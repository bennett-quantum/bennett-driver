//! Published plugin prepare/check/finalise stages for one materialised entry.
use super::*;

pub struct Adapter {
    pub plugin: PathBuf,
    pub receipt: PathBuf,
    pub entry: String,
    plugin_pin: Option<String>,
    contract: Contract,
}
pub enum Phase {
    Prepare,
    Finalise,
    HostImports,
}
impl Adapter {
    pub fn select(o: &Options, _major: u32, device: &Path) -> Result<Option<Self>> {
        let Some(entry) = o
            .get(OptionKey::ComparisonEntry)
            .or(o.get(OptionKey::Entry))
        else {
            if o.get(OptionKey::ComparisonLaunchRecord).is_some() {
                return Err(
                    "BD-E-INPUT: comparison launch record requires a selected comparison entry"
                        .into(),
                );
            }
            return Ok(None);
        };
        Ok(Some(Self {
            plugin: configured_path(o, OptionKey::Plugin)?,
            receipt: absolute(
                o.get(OptionKey::ComparisonLaunchRecord)
                    .map(PathBuf::from)
                    .unwrap_or(
                        device
                            .parent()
                            .unwrap()
                            .join(entry)
                            .join("launch-record.json"),
                    ),
            )?,
            entry: entry.into(),
            plugin_pin: o.get(OptionKey::PluginSha256).map(str::to_owned),
            contract: o.contract,
        }))
    }
    pub fn run(&self, b: &mut Build, major: u32, phase: Phase, input: &Path) -> Result<PathBuf> {
        let (stage, pass, output, report) = match phase {
            Phase::Prepare => (
                "native-prepare",
                "bennett-native-comparison",
                "native-prepared.bc",
                Some("native-preparation.json"),
            ),
            Phase::Finalise => (
                "native-finalise",
                "bennett-native-comparison-finalise",
                "native-finalised.bc",
                Some("native-materialisation.json"),
            ),
            Phase::HostImports => (
                "native-host-imports",
                "bennett-native-host-imports",
                "native-host.bc",
                None,
            ),
        };
        if matches!(phase, Phase::Prepare) {
            let plugin = artifact(&self.plugin, self.plugin_pin.as_deref())?;
            identity(b, &self.plugin, major, self.contract)?;
            b.record.set(
                "native_materialisation",
                obj([
                    ("schema", "bennett-driver-native-materialisation-1".into()),
                    ("entry", self.entry.clone().into()),
                    ("plugin", plugin),
                    ("launch_record", artifact(&self.receipt, None)?),
                    ("materialised", artifact(input, None)?),
                ]),
            );
        }
        let output = b.out.join(output);
        let mut args = vec![
            tool(major, "opt"),
            format!("-load-pass-plugin={}", self.plugin.display()),
            format!("-passes={pass}"),
            format!("-bennett-native-record={}", self.receipt.display()),
            format!("-bennett-native-entry={}", self.entry),
        ];
        if matches!(phase, Phase::Prepare) {
            args.push("-bennett-native-prepare-only".into());
        }
        if let Some(name) = report {
            args.push(format!(
                "-bennett-native-report={}",
                b.out.join(name).display()
            ));
        }
        args.extend([
            input.display().to_string(),
            "-o".into(),
            output.display().to_string(),
        ]);
        if let Err(error) = b.run(stage, args, None) {
            match fs::remove_file(&output) {
                Ok(()) => (),
                Err(cleanup) if cleanup.kind() == std::io::ErrorKind::NotFound => (),
                Err(cleanup) => {
                    return Err(format!(
                        "BD-E-NATIVE-ADAPTER: {error}; remove incomplete {}: {cleanup}",
                        output.display()
                    ));
                }
            }
            return Err(format!("BD-E-NATIVE-ADAPTER: {error}"));
        }
        b.record.set(stage, artifact(&output, None)?);
        if let Some(name) = report {
            b.record.set(
                &format!("{stage}-report"),
                artifact(&b.out.join(name), None)?,
            );
        }
        b.save("running")?;
        Ok(output)
    }
}
