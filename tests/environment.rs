mod support;

#[test]
fn external_children_keep_the_task_environment() {
    support::fixture("environment.py");
}
