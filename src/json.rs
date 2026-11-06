//! Small JSON value writer: keys are sorted, integers are exact, no network crates.
use std::collections::BTreeMap;
#[derive(Clone, Debug)]
pub enum Json {
    Bool(bool),
    Num(u64),
    Str(String),
    Array(Vec<Json>),
    Object(BTreeMap<String, Json>),
}
impl From<&str> for Json {
    fn from(s: &str) -> Self {
        Self::Str(s.into())
    }
}
impl From<String> for Json {
    fn from(s: String) -> Self {
        Self::Str(s)
    }
}
impl From<u32> for Json {
    fn from(n: u32) -> Self {
        Self::Num(n.into())
    }
}
impl From<bool> for Json {
    fn from(b: bool) -> Self {
        Self::Bool(b)
    }
}
pub fn obj(items: impl IntoIterator<Item = (impl Into<String>, Json)>) -> Json {
    Json::Object(items.into_iter().map(|(k, v)| (k.into(), v)).collect())
}
pub fn strings(items: &[String]) -> Json {
    Json::Array(items.iter().cloned().map(Json::Str).collect())
}
impl Json {
    pub fn set(&mut self, key: &str, value: Json) {
        match self {
            Self::Object(m) => {
                m.insert(key.into(), value);
            }
            _ => panic!("JSON object required"),
        }
    }
    pub fn encode(&self) -> String {
        match self {
            Self::Bool(b) => b.to_string(),
            Self::Num(n) => n.to_string(),
            Self::Str(s) => {
                let mut out = String::from("\"");
                for c in s.chars() {
                    match c {
                        '"' => out.push_str("\\\""),
                        '\\' => out.push_str("\\\\"),
                        '\n' => out.push_str("\\n"),
                        '\r' => out.push_str("\\r"),
                        '\t' => out.push_str("\\t"),
                        c if c < ' ' => out.push_str(&format!("\\u{:04x}", c as u32)),
                        c => out.push(c),
                    }
                }
                out.push('"');
                out
            }
            Self::Array(a) => format!(
                "[{}]",
                a.iter().map(Self::encode).collect::<Vec<_>>().join(",")
            ),
            Self::Object(m) => format!(
                "{{{}}}",
                m.iter()
                    .map(|(k, v)| format!("{}:{}", Self::Str(k.clone()).encode(), v.encode()))
                    .collect::<Vec<_>>()
                    .join(",")
            ),
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn json_unicode_control_characters_and_exact_integer_boundary() {
        let value = Json::Array(vec![
            "\u{8}\u{c}\r\t λ😀".into(),
            Json::Num(u64::MAX),
            false.into(),
        ]);
        assert_eq!(
            value.encode(),
            "[\"\\u0008\\u000c\\r\\t λ😀\",18446744073709551615,false]"
        );
    }
    #[test]
    fn canonical_keys_and_escapes() {
        assert_eq!(
            obj([("z", "a\n\"\\\0".into()), ("a", 1u32.into())]).encode(),
            "{\"a\":1,\"z\":\"a\\n\\\"\\\\\\u0000\"}"
        );
    }
}
