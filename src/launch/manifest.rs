//! The manifest has a closed, string-only JCS grammar (ISA 0.9 §10.1).
//! Parsing that grammar directly rejects duplicate/unknown fields and non-JCS
//! spelling without introducing a permissive general-purpose JSON reader.
pub(super) fn validate(bytes: &[u8], abi: &str) -> Result<(), String> {
    let mut reader = Reader(bytes);
    reader.take(b"{\"abi\":")?;
    if reader.string()? != abi {
        return Err(format!("expected base ABI {abi}"));
    }
    reader.take(b",\"features\":[")?;
    let mut previous = None;
    let mut supported = false;
    if !reader.0.starts_with(b"]") {
        loop {
            let feature = reader.string()?;
            if feature.is_empty() || previous.as_ref().is_some_and(|p| p >= &feature) {
                return Err(
                    "features must be nonempty ASCII identifiers in unique bytewise order".into(),
                );
            }
            supported |= feature == "token_aliases/1";
            previous = Some(feature);
            if !reader.0.starts_with(b",") {
                break;
            }
            reader.take(b",")?;
        }
    }
    reader.take(b"],\"schema\":\"bennett.abi-features/1\"}")?;
    if !reader.0.is_empty() {
        return Err("trailing manifest bytes".into());
    }
    if !supported {
        return Err("missing token_aliases/1".into());
    }
    Ok(())
}
struct Reader<'a>(&'a [u8]);
impl Reader<'_> {
    fn take(&mut self, prefix: &[u8]) -> Result<(), String> {
        self.0 = self
            .0
            .strip_prefix(prefix)
            .ok_or("malformed/non-JCS manifest or unsupported schema")?;
        Ok(())
    }
    fn string(&mut self) -> Result<String, String> {
        self.take(b"\"")?;
        let mut result = String::new();
        loop {
            let (&byte, rest) = self.0.split_first().ok_or("unterminated manifest string")?;
            self.0 = rest;
            match byte {
                b'"' => return Ok(result),
                b'\\' => result.push(self.escape()? as char),
                32..=127 => result.push(byte as char),
                _ => return Err("manifest identifiers must be ASCII with JCS escapes".into()),
            }
        }
    }
    fn escape(&mut self) -> Result<u8, String> {
        let (&byte, rest) = self.0.split_first().ok_or("unterminated escape")?;
        self.0 = rest;
        match byte {
            b'"' | b'\\' => Ok(byte),
            b'b' => Ok(8),
            b't' => Ok(9),
            b'n' => Ok(10),
            b'f' => Ok(12),
            b'r' => Ok(13),
            b'u' => {
                self.take(b"00")?;
                let digits = self.0.get(..2).ok_or("short Unicode escape")?;
                if !digits
                    .iter()
                    .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(b))
                {
                    return Err("noncanonical Unicode escape".into());
                }
                let text = std::str::from_utf8(digits).map_err(|e| e.to_string())?;
                let value = u8::from_str_radix(text, 16).map_err(|e| e.to_string())?;
                if value >= 32 || matches!(value, 8..=10 | 12..=13) {
                    return Err("noncanonical Unicode escape".into());
                }
                self.0 = &self.0[2..];
                Ok(value)
            }
            _ => Err("non-JCS string escape".into()),
        }
    }
}
