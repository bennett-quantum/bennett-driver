//! Admit destinations before any comparison writes or native code generation.
use super::*;
use std::os::unix::fs::MetadataExt;

/// Prior build stages have already published these bytes and hashes. Comparison
/// destinations must preserve them just like external source/library inputs.
pub fn recorded_artifacts(value: &Json, paths: &mut Vec<PathBuf>) {
    match value {
        Json::Object(fields) => {
            if let (Some(Json::Str(path)), Some(Json::Str(_))) =
                (fields.get("path"), fields.get("sha256"))
            {
                paths.push(PathBuf::from(path));
            }
            for value in fields.values() {
                recorded_artifacts(value, paths);
            }
        }
        Json::Array(values) => {
            for value in values {
                recorded_artifacts(value, paths);
            }
        }
        _ => {}
    }
}

/// Protect the complete prior-stage inventory, including entry evidence that
/// is not represented by a path/hash pair in the driver manifest.
pub fn published_artifacts(directory: &Path, paths: &mut Vec<PathBuf>) -> Result<()> {
    let inventory_error = |error| {
        format!(
            "BD-E-OUTPUT-PATH: cannot inventory {}: {error}",
            directory.display()
        )
    };
    let entries = fs::read_dir(directory)
        .and_then(|entries| entries.collect::<std::io::Result<Vec<_>>>())
        .map_err(inventory_error)?;
    for entry in entries {
        let path = entry.path();
        if entry.file_type().map_err(inventory_error)?.is_dir() {
            published_artifacts(&path, paths)?;
        }
        paths.push(path);
    }
    Ok(())
}

fn resolved(path: &Path) -> Result<PathBuf> {
    match fs::canonicalize(path) {
        Ok(path) => Ok(path),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            let parent = path
                .parent()
                .ok_or_else(|| format!("BD-E-OUTPUT-PATH: cannot resolve {}", path.display()))?;
            let name = path
                .file_name()
                .ok_or_else(|| format!("BD-E-OUTPUT-PATH: cannot resolve {}", path.display()))?;
            Ok(resolved(parent)?.join(name))
        }
        Err(error) => Err(format!(
            "BD-E-OUTPUT-PATH: cannot resolve {}: {error}",
            path.display()
        )),
    }
}

pub fn admit(inputs: &[PathBuf], outputs: &[(&str, PathBuf)]) -> Result<()> {
    let aliases = |a: &Path, b: &Path| -> Result<bool> {
        if resolved(a)? == resolved(b)? {
            return Ok(true);
        }
        Ok(match (fs::metadata(a), fs::metadata(b)) {
            (Ok(a), Ok(b)) => a.dev() == b.dev() && a.ino() == b.ino(),
            _ => false,
        })
    };
    for (index, (role, path)) in outputs.iter().enumerate() {
        let protected = inputs.iter().map(|input| ("input".into(), input)).chain(
            outputs[..index]
                .iter()
                .map(|(role, path)| (format!("{role} destination"), path)),
        );
        for (other_role, other) in protected {
            if aliases(path, other)? {
                return Err(format!(
                    "BD-E-OUTPUT-PATH: {role} destination {} aliases {other_role} {}",
                    path.display(),
                    other.display()
                ));
            }
        }
    }
    Ok(())
}
