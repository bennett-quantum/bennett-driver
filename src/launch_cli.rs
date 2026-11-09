//! Runnable startup adapter for tuple-resolved alias-aware estimates. Each group
//! selects one device object/root/provider; it does not describe a host binary.
use bennett_driver::launch::{DeviceRoot, LaunchShim, Provider};
use std::{collections::BTreeMap, ffi::CString, fs, io::Write, path::PathBuf};
type Result<T> = std::result::Result<T, String>;
#[derive(Clone, Copy, Eq, Ord, PartialEq, PartialOrd)]
enum Key {
    Provider,
    Root,
    Object,
    Region,
    Target,
    Budget,
    Variant,
    Controls,
    Params,
    Aliases,
    Certificate,
}
impl Key {
    fn parse(name: &str) -> Result<Self> {
        match name {
            "provider" => Ok(Self::Provider),
            "root" => Ok(Self::Root),
            "object" => Ok(Self::Object),
            "region" => Ok(Self::Region),
            "target" => Ok(Self::Target),
            "budget" => Ok(Self::Budget),
            "variant" => Ok(Self::Variant),
            "controls" => Ok(Self::Controls),
            "params" => Ok(Self::Params),
            "aliases" => Ok(Self::Aliases),
            "certificate" => Ok(Self::Certificate),
            _ => Err(format!("unknown launch-estimate option --{name}")),
        }
    }
}
struct Request {
    provider: PathBuf,
    root: DeviceRoot,
    target: Vec<u8>,
    budget: [u64; 4],
    variant: CString,
    controls: u32,
    params: Vec<u8>,
    aliases: Vec<u8>,
    certificate: PathBuf,
}
impl Request {
    fn parse(args: &[String]) -> Result<Self> {
        let mut values = BTreeMap::new();
        for argument in args {
            let (name, value) = argument
                .strip_prefix("--")
                .and_then(|s| s.split_once('='))
                .ok_or_else(|| format!("expected --NAME=VALUE in launch-estimate: {argument}"))?;
            let key = Key::parse(name)?;
            if value.is_empty() || values.insert(key, value).is_some() {
                return Err(format!("empty/duplicate launch-estimate option --{name}"));
            }
        }
        let required = |key, name| {
            values
                .get(&key)
                .copied()
                .ok_or_else(|| format!("missing launch-estimate --{name}=VALUE"))
        };
        let bytes = |key, name| {
            let path = required(key, name)?;
            fs::read(path).map_err(|e| format!("read {path}: {e}"))
        };
        let cstring =
            |key, name| CString::new(required(key, name)?).map_err(|e| format!("--{name}: {e}"));
        let budget = required(Key::Budget, "budget")?
            .split(',')
            .map(|n| n.parse::<u64>().map_err(|e| format!("--budget: {e}")))
            .collect::<Result<Vec<_>>>()?;
        let budget = budget
            .try_into()
            .map_err(|_| "--budget requires steps,heap,stack,depth".to_string())?;
        let certificate = PathBuf::from(required(Key::Certificate, "certificate")?);
        match fs::symlink_metadata(&certificate) {
            Ok(_) => {
                return Err(format!(
                    "certificate output already exists: {}",
                    certificate.display()
                ));
            }
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
            Err(e) => return Err(format!("certificate {}: {e}", certificate.display())),
        }
        Ok(Self {
            provider: required(Key::Provider, "provider")?.into(),
            root: DeviceRoot {
                name: required(Key::Root, "root")?.into(),
                object: bytes(Key::Object, "object")?,
                region: cstring(Key::Region, "region")?,
            },
            target: bytes(Key::Target, "target")?,
            budget,
            variant: cstring(Key::Variant, "variant")?,
            controls: required(Key::Controls, "controls")?
                .parse()
                .map_err(|e| format!("--controls: {e}"))?,
            params: bytes(Key::Params, "params")?,
            aliases: bytes(Key::Aliases, "aliases")?,
            certificate,
        })
    }
    fn execute(&self) -> Result<()> {
        // Native provider code is selected explicitly by the host invocation.
        let provider = unsafe { Provider::open(&self.provider) }
            .map_err(|e| format!("device root {}: {e}", self.root.name))?;
        let shim =
            LaunchShim::load(&provider, &self.root, &self.target).map_err(|e| e.to_string())?;
        let token = shim.budget(self.budget).map_err(|e| e.to_string())?;
        let estimate = shim
            .estimate(
                &token,
                &self.variant,
                self.controls,
                &self.params,
                &self.aliases,
            )
            .map_err(|e| e.to_string())?;
        let mut output = fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&self.certificate)
            .map_err(|e| format!("certificate {}: {e}", self.certificate.display()))?;
        output
            .write_all(estimate.certificate())
            .map_err(|e| format!("certificate {}: {e}", self.certificate.display()))
    }
}
pub(super) fn run(args: &[String]) -> Result<()> {
    let requests = args
        .split(|s| s == "--next-root")
        .map(Request::parse)
        .collect::<Result<Vec<_>>>()?;
    for request in requests {
        request.execute()?;
    }
    Ok(())
}
