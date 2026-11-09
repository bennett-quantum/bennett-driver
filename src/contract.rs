//! Explicit compatibility tracks: dialect §19.9 and §23, R profile §1.7.
use super::*;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(super) enum Contract {
    Historical10,
    Published13,
    ClassicalR,
}
impl Contract {
    pub(super) fn select(dialect: Option<&str>, isa: Option<&str>) -> Result<Self> {
        let contract = match dialect {
            Some("0.2.10") => Self::Historical10,
            Some("0.2.13") => Self::Published13,
            Some("0.3-r1") => Self::ClassicalR,
            _ => return Err(Self::version_error(dialect, isa)),
        };
        if isa.is_some_and(|isa| isa != contract.versions().1) {
            return Err(Self::version_error(dialect, isa));
        }
        Ok(contract)
    }
    fn version_error(dialect: Option<&str>, isa: Option<&str>) -> String {
        format!(
            "BD-E-VERSION: required dialect 0.2.13 (or explicit historical 0.2.10) and ISA 0.8, or dialect 0.3-r1 and ISA 0.9; requested dialect {dialect:?}, ISA {isa:?}"
        )
    }
    pub(super) fn versions(self) -> (&'static str, &'static str) {
        match self {
            Self::Historical10 => ("0.2.10", "0.8"),
            Self::Published13 => ("0.2.13", "0.8"),
            Self::ClassicalR => ("0.3-r1", "0.9"),
        }
    }
    pub(super) fn identity(self) -> String {
        let (dialect, isa) = self.versions();
        format!("dialect-{dialect};isa-{isa}")
    }
    pub(super) fn record(self) -> Json {
        let (dialect, isa) = self.versions();
        let mut record = obj([("dialect", dialect.into()), ("isa", isa.into())]);
        if self == Self::ClassicalR {
            // R-contract identity overrides, dialect §19.9. finalise-build
            // binds this manifest into the certificate's producer.version.
            record.set("dialect_version", dialect.into());
            record.set("isa_version", isa.into());
            record.set("replay_profile", "saved-tape-v1".into());
        }
        record
    }
}
