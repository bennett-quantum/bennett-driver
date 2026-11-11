use super::*;
macro_rules! option_keys {
    ($($variant:ident => $name:literal),+ $(,)?) => {
        #[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
        pub(super) enum OptionKey { $($variant),+ }
        impl OptionKey {
            pub(super) fn parse(key: &str, original: &str) -> Result<Self> {
                match key {
                    $($name => Ok(Self::$variant),)+
                    _ => Err(format!("BD-E-INPUT: unimplemented driver option {original}; capability remains required by dialect §19")),
                }
            }
            pub(super) fn as_str(self) -> &'static str {
                match self { $(Self::$variant => $name),+ }
            }
        }
        impl std::fmt::Display for OptionKey {
            fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
                f.write_str(self.as_str())
            }
        }
    };
}
option_keys! {
    AnalysisBudgetMs => "bennett-analysis-budget-ms",
    ArenaHeap => "bennett-arena-heap",
    ArgvReplies => "bennett-argv-replies",
    ProcessArguments => "bennett-process-arguments",
    Arith => "bennett-arith",
    ArithGenerator => "bennett-arith-generator",
    Bind => "bennett-bind",
    BudgetDefault => "bennett-budget-default",
    Budgets => "bennett-budgets",
    Class => "bennett-class",
    ClassifierInput => "bennett-classifier-input",
    ClosedUnit => "bennett-closed-unit",
    Comparison => "bennett-comparison",
    ComparisonEntry => "bennett-comparison-entry",
    ComparisonLaunchRecord => "bennett-comparison-launch-record",
    ComparisonLayout => "bennett-comparison-layout",
    ComparisonOutput => "bennett-comparison-output",
    ComparisonRecord => "bennett-comparison-record",
    Cpu => "bennett-cpu",
    Dev => "bennett-dev",
    Dialect => "bennett-dialect",
    Disk => "bennett-disk",
    Emit => "bennett-emit",
    Entry => "bennett-entry",
    InplaceExhaustiveBits => "bennett-inplace-exhaustive-bits",
    Isa => "bennett-isa",
    LayoutDataBase => "bennett-layout-data-base",
    LayoutTextBase => "bennett-layout-text-base",
    LlvmMajor => "bennett-llvm-major",
    Materialised => "bennett-materialised",
    NativeProvider => "bennett-native-provider",
    NativeTarget => "bennett-native-target",
    NativeBackend => "bennett-native-backend",
    NativeCheck => "bennett-native-check",
    NativeInput => "bennett-native-input",
    NativeSupport => "bennett-native-support",
    Oracle => "bennett-oracle",
    Out => "bennett-out",
    Payload => "bennett-payload",
    Pipeline => "bennett-pipeline",
    Platform => "bennett-platform",
    PlatformRam => "bennett-platform-ram",
    Plugin => "bennett-plugin",
    QregInstances => "bennett-qreg-instances",
    Runtimes => "bennett-runtimes",
    Snapshot => "bennett-snapshot",
    Sysroot => "bennett-sysroot",
    Tier => "bennett-tier",
    Vscale => "bennett-vscale",
    WarnQstore => "bennett-warn-qstore",
    ArithGeneratorSha256 => "bennett-arith-generator-sha256",
    ArithSha256 => "bennett-arith-sha256",
    NativeCheckSha256 => "bennett-native-check-sha256",
    NativeSupportSha256 => "bennett-native-support-sha256",
    PluginSha256 => "bennett-plugin-sha256",
    RuntimesSha256 => "bennett-runtimes-sha256",
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(super) enum Tier {
    Reversible,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(super) enum Emission {
    Artifact,
    ProcessBitcode,
}
#[derive(Debug)]
pub(super) struct PluginArgument {
    pub(super) key: OptionKey,
    pub(super) value: String,
}
impl std::fmt::Display for PluginArgument {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let prefix = match self.key {
            OptionKey::Tier | OptionKey::Entry | OptionKey::Disk => "--",
            _ => "-",
        };
        write!(f, "{prefix}{}={}", self.key, self.value)
    }
}
#[derive(Debug)]
pub(super) struct Options {
    pub(super) contract: Contract,
    pub(super) values: BTreeMap<OptionKey, String>,
    pub(super) paths: BTreeMap<OptionKey, PathBuf>,
    pub(super) sysroot: Option<Sysroot>,
    pub(super) inputs: Vec<PathBuf>,
    pub(super) plugin_args: Vec<PluginArgument>,
    pub(super) major: u32,
    pub(super) comparison: bool,
    pub(super) tier: Option<Tier>,
    pub(super) emission: Emission,
    pub(super) pipeline: String,
    pub(super) data_base: String,
}
impl Options {
    pub(super) fn parse(args: &[String]) -> Result<Self> {
        let mut o = Self {
            contract: Contract::Published13,
            values: BTreeMap::new(),
            paths: BTreeMap::new(),
            sysroot: None,
            inputs: vec![],
            plugin_args: vec![],
            major: 23,
            comparison: false,
            tier: None,
            emission: Emission::Artifact,
            pipeline: "lto<O3>".into(),
            data_base: "4096".into(),
        };
        let mut positional = false;
        for arg in args {
            if arg == "--" {
                positional = true;
                continue;
            }
            if !positional && arg.starts_with('-') {
                let clean = arg.trim_start_matches('-');
                let (key, value) = match clean.split_once('=') {
                    Some(pair) => pair,
                    None if matches!(clean, "bennett-closed-unit" | "bennett-warn-qstore") => {
                        (clean, "true")
                    }
                    None => return Err(format!("BD-E-INPUT: option requires =value: {arg}")),
                };
                let key = OptionKey::parse(key, arg)?;
                let pass = matches!(
                    key,
                    OptionKey::BudgetDefault
                        | OptionKey::LayoutDataBase
                        | OptionKey::LayoutTextBase
                        | OptionKey::AnalysisBudgetMs
                        | OptionKey::Budgets
                        | OptionKey::Tier
                        | OptionKey::Entry
                        | OptionKey::Disk
                        | OptionKey::Oracle
                        | OptionKey::Bind
                        | OptionKey::Dev
                        | OptionKey::Payload
                        | OptionKey::Snapshot
                        | OptionKey::ClosedUnit
                        | OptionKey::Platform
                        | OptionKey::PlatformRam
                        | OptionKey::Class
                        | OptionKey::Vscale
                        | OptionKey::Cpu
                        | OptionKey::QregInstances
                        | OptionKey::InplaceExhaustiveBits
                        | OptionKey::WarnQstore
                        | OptionKey::ArenaHeap
                );
                if value.is_empty() {
                    return Err(format!("BD-E-INPUT: empty option {key}"));
                }
                if matches!(key, OptionKey::ClosedUnit | OptionKey::WarnQstore)
                    && !matches!(value, "true" | "false")
                {
                    return Err(format!("BD-E-INPUT: {key} requires true|false"));
                }
                let repeatable = matches!(key, OptionKey::Bind | OptionKey::Dev | OptionKey::Class);
                if o.values.contains_key(&key) && !repeatable {
                    return Err(format!("BD-E-INPUT: empty or duplicate option {key}"));
                }
                o.values.entry(key).or_insert_with(|| value.into());
                if pass {
                    o.plugin_args.push(PluginArgument {
                        key,
                        value: value.into(),
                    });
                }
            } else {
                o.inputs.push(PathBuf::from(arg));
            }
        }
        let adapter = o.get(OptionKey::Materialised).is_some();
        if let Some(emit) = o.get(OptionKey::Emit)
            && (emit != "process-bitcode"
                || adapter
                || o.get(OptionKey::Tier) != Some("reversible")
                || o.get(OptionKey::Comparison) == Some("true"))
        {
            return Err("BD-E-INPUT: --bennett-emit=process-bitcode requires a reversible process entry and excludes materialised/comparison mode".into());
        }
        if adapter && o.get(OptionKey::Dialect).is_none() {
            o.values.insert(OptionKey::Dialect, DIALECT.into());
        }
        if adapter && o.get(OptionKey::Out).is_none() {
            let path = Path::new(o.get(OptionKey::Materialised).unwrap())
                .parent()
                .unwrap_or(Path::new("."));
            let out = path.join("native-work").display().to_string();
            o.values.insert(OptionKey::Out, out);
        }
        o.contract = Contract::select(o.get(OptionKey::Dialect), o.get(OptionKey::Isa))?;
        if o.get(OptionKey::Out).is_none() || (o.inputs.is_empty() && !adapter) {
            return Err("BD-E-INPUT: -bennett-out and at least one input required".into());
        }
        o.major = match o.get(OptionKey::LlvmMajor).unwrap_or("23") {
            "18" => 18,
            "23" => 23,
            value => {
                return Err(format!(
                    "BD-E-VERSION: unsupported envelope LLVM major {value}; expected 18 or 23"
                ));
            }
        };
        if let Some(value) = o.get(OptionKey::Comparison)
            && !matches!(value, "true" | "false")
        {
            return Err("BD-E-INPUT: --bennett-comparison=true|false required".into());
        }
        if o.get(OptionKey::Pipeline)
            .is_some_and(|p| p.contains("view-"))
        {
            return Err("BD-E-INPUT: LLVM view-* is forbidden in headless mode".into());
        }
        if !adapter
            && o.get(OptionKey::Comparison) != Some("true")
            && o.values.keys().any(|k| {
                matches!(
                    k,
                    OptionKey::NativeProvider
                        | OptionKey::NativeTarget
                        | OptionKey::NativeInput
                        | OptionKey::NativeBackend
                        | OptionKey::NativeSupport
                        | OptionKey::NativeSupportSha256
                        | OptionKey::NativeCheck
                        | OptionKey::NativeCheckSha256
                        | OptionKey::ClassifierInput
                        | OptionKey::ComparisonLayout
                        | OptionKey::ComparisonEntry
                        | OptionKey::ComparisonLaunchRecord
                        | OptionKey::ComparisonRecord
                        | OptionKey::ComparisonOutput
                )
            })
        {
            return Err("BD-E-INPUT: comparison options require --bennett-comparison=true or --bennett-materialised".into());
        }
        o.check_process_arguments()?;
        if let Some(tier) = o.get(OptionKey::Tier) {
            if tier != "reversible" || o.get(OptionKey::Entry).is_none() {
                return Err("BD-E-INPUT: §19.2 requires --bennett-tier=reversible and --bennett-entry=SYMBOL".into());
            }
        } else if o.get(OptionKey::Entry).is_some() {
            return Err("BD-E-INPUT: --bennett-entry requires --bennett-tier=reversible".into());
        }
        for key in [
            OptionKey::Plugin,
            OptionKey::Runtimes,
            OptionKey::Arith,
            OptionKey::ArithGenerator,
            OptionKey::NativeCheck,
            OptionKey::NativeSupport,
            OptionKey::NativeProvider,
            OptionKey::NativeTarget,
        ] {
            if let Some(path) = resolve_path(&o, key)? {
                o.paths.insert(key, path);
            }
        }
        if o.paths.contains_key(&OptionKey::NativeTarget)
            != o.paths.contains_key(&OptionKey::NativeProvider)
        {
            return Err(
                "BD-E-CONFIG: select both --bennett-native-provider and --bennett-native-target"
                    .into(),
            );
        }
        o.sysroot = resolve_path(&o, OptionKey::Sysroot)?
            .map(Sysroot::new)
            .transpose()?;
        o.comparison = o.get(OptionKey::Comparison) == Some("true");
        o.tier = o.get(OptionKey::Tier).map(|_| Tier::Reversible);
        o.emission = if o.get(OptionKey::Emit).is_some() {
            Emission::ProcessBitcode
        } else {
            Emission::Artifact
        };
        o.pipeline = o.get(OptionKey::Pipeline).unwrap_or("lto<O3>").into();
        o.data_base = o.get(OptionKey::LayoutDataBase).unwrap_or("4096").into();
        Ok(o)
    }
    fn check_process_arguments(&self) -> Result<()> {
        if (self.get(OptionKey::ArgvReplies).is_some()
            || self.get(OptionKey::ProcessArguments).is_some())
            && self.get(OptionKey::Tier) != Some("reversible")
        {
            return Err(
                "BD-E-INPUT: process arguments/argv replies require --bennett-tier=reversible"
                    .into(),
            );
        }
        if self.get(OptionKey::ArgvReplies).is_some()
            && self.get(OptionKey::ProcessArguments).is_some()
        {
            return Err("BD-E-INPUT: choose process arguments or explicit argv replies".into());
        }
        Ok(())
    }
    pub(super) fn get(&self, key: OptionKey) -> Option<&str> {
        self.values.get(&key).map(String::as_str)
    }
    pub(super) fn dialect(&self) -> &str {
        self.contract.versions().0
    }
    pub(super) fn isa(&self) -> &str {
        self.contract.versions().1
    }
    pub(super) fn required_sysroot(&self) -> Result<&Sysroot> {
        self.sysroot.as_ref().ok_or_else(|| {
            "BD-E-CONFIG: missing --bennett-sysroot=PATH or BENNETT_DRIVER_SYSROOT".into()
        })
    }
}
