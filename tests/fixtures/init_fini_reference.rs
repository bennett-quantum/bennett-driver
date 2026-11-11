//! Audit callback effects and exact restoration through the published reference API.
use bennett_isa_ref::{json::Json, ClassicalMachine, ClassicalValue, Object};
use std::{env, fs};
fn hex(text: &str) -> Vec<u8> {
    text.as_bytes()
        .chunks_exact(2)
        .map(|p| u8::from_str_radix(std::str::from_utf8(p).unwrap(), 16).unwrap())
        .collect()
}
fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let object = Object::parse(&fs::read_to_string(&args[0]).unwrap()).unwrap();
    object.check_hashes().unwrap();
    let replies = Json::parse(&fs::read_to_string(&args[1]).unwrap()).unwrap();
    let mut machine = ClassicalMachine::new(&object, "main", &[], &[]).unwrap();
    let initial = machine.snapshot();
    for row in replies.array().unwrap() {
        let outcome = machine.run(1_000_000).unwrap();
        assert_eq!(outcome.fault, None);
        let request = outcome.request.expect("published byte import");
        assert_eq!(
            request.service,
            row.get("service").unwrap().string().unwrap()
        );
        assert_eq!(
            &*request.payload,
            hex(row.get("payload").unwrap().string().unwrap())
        );
        machine
            .reply(&hex(row.get("reply").unwrap().string().unwrap()))
            .unwrap();
    }
    let outcome = machine.run(1_000_000).unwrap();
    assert_eq!(outcome.fault, None);
    assert!(outcome.request.is_none());
    assert_eq!(&*outcome.values, &[ClassicalValue::Int(32, 7)]);
    assert_eq!(machine.console(), args[2].as_bytes());
    machine.reverse().unwrap();
    let restored = machine.snapshot();
    assert_eq!(restored.first_difference(&initial), None);
    assert!(restored.memory_equals(&initial));
    assert_eq!(machine.console(), b"");
    println!("actual callbacks, exit7, exact console and complete memory restoration");
}
