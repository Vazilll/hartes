pub mod pruner;
pub mod stats;

use pyo3::prelude::*;
use pyo3::types::PyDict;
use pruner::{DocstringMode, NativeTreeSitterPruner};
use stats::PruningStats;

/// Pure Rust entrypoint for pruning Python source code.
pub fn prune_code_string(source_code: &str, docstring_mode: &str) -> (String, PruningStats) {
    let mode = DocstringMode::from_str(docstring_mode);
    let pruner = NativeTreeSitterPruner::new(mode);
    pruner.prune(source_code)
}

#[pyfunction]
#[pyo3(name = "prune_code_string", signature = (source_code, docstring_mode = "summary"))]
fn py_prune_code_string<'py>(
    py: Python<'py>,
    source_code: &str,
    docstring_mode: &str,
) -> PyResult<(String, Bound<'py, PyDict>)> {
    // Release the Python GIL during parsing and skeleton synthesis
    let (pruned_code, stats) = py.allow_threads(|| prune_code_string(source_code, docstring_mode));

    let dict = PyDict::new(py);
    dict.set_item("is_valid", stats.is_valid)?;
    dict.set_item("language", stats.language)?;
    dict.set_item("total_nodes", stats.total_nodes)?;
    dict.set_item("pruned_nodes", stats.pruned_nodes)?;
    dict.set_item("nodes_removed", stats.nodes_removed)?;
    dict.set_item("reduction_percent", stats.reduction_percent)?;
    dict.set_item("reduction_percentage", stats.reduction_percentage)?;
    dict.set_item("orig_bytes", stats.orig_bytes)?;
    dict.set_item("pruned_bytes", stats.pruned_bytes)?;

    Ok((pruned_code, dict))
}

#[pymodule]
fn vazus_native_ast(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(py_prune_code_string, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_simple_function() {
        let code = "def test():\n    pass";
        let (pruned, stats) = prune_code_string(code, "summary");
        assert!(stats.is_valid);
        assert_eq!(pruned, "def test():\n    ...");
    }

    #[test]
    fn test_return_statement_preserved() {
        let code = "def compute(x: int, y: int = 10) -> int:\n    temp = x * 2\n    res = temp + y\n    return res";
        let (pruned, stats) = prune_code_string(code, "summary");
        assert!(stats.is_valid);
        assert!(pruned.contains("def compute(x: int, y: int=10) -> int:"));
        assert!(pruned.contains("return res"));
        assert!(!pruned.contains("temp = x * 2"));
    }

    #[test]
    fn test_docstring_summary_and_contracts() {
        let code = "def solve(n: int) -> int:\n    \"\"\"\n    Calculate solution.\n    :requires: n > 0\n    :ensures: result > n\n    More verbose text here.\n    \"\"\"\n    return n + 1";
        let (pruned, stats) = prune_code_string(code, "summary");
        assert!(stats.is_valid);
        assert!(pruned.contains("Calculate solution."));
        assert!(pruned.contains(":requires: n > 0"));
        assert!(pruned.contains(":ensures: result > n"));
        assert!(!pruned.contains("More verbose text here."));
    }

    #[test]
    fn test_class_pruning() {
        let code = r#"
class DataProcessor:
    """Processes incoming data frames with vector embeddings."""
    
    def __init__(self, name: str, batch_size: int = 64) -> None:
        """Initialize DataProcessor with configuration."""
        self.name = name
        self.batch_size = batch_size
        self.data_store = []

    def _private_helper(self):
        return 42

    def process(self, item: dict) -> dict:
        return item
"#;
        let (pruned, stats) = prune_code_string(code, "summary");
        assert!(stats.is_valid);
        assert!(pruned.contains("class DataProcessor:"));
        assert!(pruned.contains("def __init__(self, name: str, batch_size: int=64) -> None:"));
        assert!(pruned.contains("\"\"\"Initialize DataProcessor with configuration.\"\"\""));
        assert!(pruned.contains("..."));
        assert!(pruned.contains("def process(self, item: dict) -> dict:"));
        assert!(pruned.contains("return item"));
        assert!(!pruned.contains("_private_helper"));
    }

    #[test]
    fn test_top_level_try_except_and_if() {
        let code = r#"
try:
    import sqlite_vec
except ImportError:
    sqlite_vec = None

if True:
    CONSTANT = 1
else:
    CONSTANT = 2

def my_func():
    return 42
"#;
        let (pruned, stats) = prune_code_string(code, "summary");
        assert!(stats.is_valid);
        assert!(pruned.contains("try:"));
        assert!(pruned.contains("import sqlite_vec"));
        assert!(pruned.contains("except ImportError:"));
        assert!(pruned.contains("sqlite_vec = None"));
        assert!(pruned.contains("def my_func():"));
    }

    #[test]
    fn test_utf8_comment_slicing() {
        let code = "class МетрикиКачества: # коммент\n    pass\n";
        let (pruned, stats) = prune_code_string(code, "summary");
        assert!(stats.is_valid);
        assert!(pruned.contains("class МетрикиКачества:"));
    }

    #[test]
    fn test_syntax_error_detection() {
        let malformed = "def unclosed_function(:\n    return 42";
        let (_pruned, stats) = prune_code_string(malformed, "summary");
        assert!(!stats.is_valid);
    }

    #[test]
    fn test_nested_classes_and_closures() {
        let code = "@decorator_a\nclass Outer:\n    class Inner:\n        @decorator_b\n        async def nested_async(self, p: str) -> bool:\n            val = await fetch(p)\n            return bool(val)\n";
        let (pruned, stats) = prune_code_string(code, "summary");
        assert!(stats.is_valid);
        assert!(pruned.contains("class Outer:"));
        assert!(pruned.contains("class Inner:"));
        assert!(pruned.contains("nested_async"));
        assert!(pruned.contains("return bool(val)"));
    }

    #[test]
    fn test_closure_return_not_stolen() {
        let code = "def outer():\n    def inner():\n        return 999\n    return 1\n";
        let (pruned, stats) = prune_code_string(code, "summary");
        assert!(stats.is_valid);
        assert!(pruned.contains("return 1"));
        assert!(!pruned.contains("return 999"));
    }

    #[test]
    fn test_inline_function_body() {
        let code = "def test(): pass";
        let (pruned, stats) = prune_code_string(code, "summary");
        assert!(stats.is_valid);
        assert_eq!(pruned, "def test():\n    ...");
    }
}



