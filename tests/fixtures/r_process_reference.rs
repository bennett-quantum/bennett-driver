//! Execute the unchanged process with the pinned reference library binary.
use bennett_isa_ref::{json::Json, ClassicalMachine, ClassicalValue, Object};
use std::{env, fs};

fn hex(text: &str) -> Vec<u8> {
    assert_eq!(text.len() % 2, 0);
    text.as_bytes()
        .chunks_exact(2)
        .map(|pair| u8::from_str_radix(std::str::from_utf8(pair).unwrap(), 16).unwrap())
        .collect()
}

fn main() {
    let arguments = env::args().skip(1).collect::<Vec<_>>();
    assert_eq!(arguments.len(), 2);
    let object = Object::parse(&fs::read_to_string(&arguments[0]).unwrap()).unwrap();
    object.check_hashes().unwrap();
    let replies = Json::parse(&fs::read_to_string(&arguments[1]).unwrap()).unwrap();
    let replies = replies.array().unwrap();
    let mut machine = ClassicalMachine::new(&object, "main", &[], &[]).unwrap();
    let initial = machine.snapshot();
    for row in replies {
        let outcome = machine.run(1_000_000).unwrap();
        assert_eq!(outcome.fault, None);
        let request = outcome.request.expect("expected published host request");
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
    assert_eq!(machine.console(), b"abc\nbye\n");
    assert_eq!(machine.host_exchanges().count(), 2);
    machine.reverse().unwrap();
    let restored = machine.snapshot();
    assert_eq!(restored.first_difference(&initial), None);
    assert!(restored.memory_equals(&initial));
    assert_eq!(machine.console(), b"");
    println!("exit7; abc+bye; two exact byte imports; full entry and memory restored");
}
