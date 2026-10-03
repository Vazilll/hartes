pub mod parallel;
pub mod solver;
pub mod z3_ffi;

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use solver::{verify_functional_equivalence, verify_memory_safety, verify_contract_code, NativeVerificationResult};

#[pyfunction]
#[pyo3(name = "verify_memory_safety")]
fn py_verify_memory_safety(offset: i64, length: i64, capacity: i64) -> NativeVerificationResult {
    verify_memory_safety(offset, length, capacity)
}

#[pyfunction]
#[pyo3(name = "verify_memory_safety_native")]
fn py_verify_memory_safety_native(offset: i64, length: i64, capacity: i64) -> NativeVerificationResult {
    verify_memory_safety(offset, length, capacity)
}

#[pyfunction]
#[pyo3(name = "verify_functional_equivalence_native", signature = (orig_code, opt_code, func_name = "f"))]
fn py_verify_functional_equivalence_native(
    py: Python<'_>,
    orig_code: &str,
    opt_code: &str,
    func_name: &str,
) -> NativeVerificationResult {
    py.allow_threads(|| verify_functional_equivalence(orig_code, opt_code, func_name))
}

#[pyfunction]
#[pyo3(name = "verify_code_contracts_native")]
fn py_verify_code_contracts_native(py: Python<'_>, code: &str) -> NativeVerificationResult {
    py.allow_threads(|| verify_contract_code(code))
}

#[pyfunction]
#[pyo3(name = "verify_contracts_parallel")]
fn py_verify_contracts_parallel(py: Python<'_>, contracts_json: &str) -> PyResult<String> {
    py.allow_threads(|| {
        parallel::verify_contracts_parallel_str(contracts_json)
            .map_err(|e| PyValueError::new_err(e))
    })
}

#[pymodule]
fn vazus_native_z3(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<NativeVerificationResult>()?;
    m.add_function(wrap_pyfunction!(py_verify_memory_safety, m)?)?;
    m.add_function(wrap_pyfunction!(py_verify_memory_safety_native, m)?)?;
    m.add_function(wrap_pyfunction!(py_verify_functional_equivalence_native, m)?)?;
    m.add_function(wrap_pyfunction!(py_verify_code_contracts_native, m)?)?;
    m.add_function(wrap_pyfunction!(py_verify_contracts_parallel, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_verify_memory_safety_bounds() {
        let res_valid = verify_memory_safety(10, 20, 100);
        assert!(res_valid.verified);
        assert_eq!(res_valid.smt_solver_status, "UNSAT");

        let res_exact = verify_memory_safety(0, 100, 100);
        assert!(res_exact.verified);
        assert_eq!(res_exact.smt_solver_status, "UNSAT");

        let res_oob = verify_memory_safety(90, 20, 100);
        assert!(!res_oob.verified);
        assert_eq!(res_oob.smt_solver_status, "SAT");
        assert!(res_oob.counterexample.is_some());

        let res_neg = verify_memory_safety(-5, 10, 100);
        assert!(!res_neg.verified);
        assert_eq!(res_neg.smt_solver_status, "SAT");
    }

    #[test]
    fn test_functional_equivalence_double() {
        let orig = "def double_val(x: int) -> int:\n    return x + x\n";
        let opt = "def double_val(x: int) -> int:\n    return x * 2\n";
        let res = verify_functional_equivalence(orig, opt, "double_val");
        assert!(res.verified);
        assert_eq!(res.smt_solver_status, "UNSAT");
        assert!(res.counterexample.is_none());
    }

    #[test]
    fn test_functional_equivalence_polynomial() {
        let orig = "def poly_identity(x: int, y: int) -> int:\n    return (x + y) * (x - y)\n";
        let opt = "def poly_identity(x: int, y: int) -> int:\n    return x**2 - y**2\n";
        let res = verify_functional_equivalence(orig, opt, "poly_identity");
        assert!(res.verified);
        assert_eq!(res.smt_solver_status, "UNSAT");
        assert!(res.counterexample.is_none());
    }

    #[test]
    fn test_functional_equivalence_counterexample() {
        let orig = "def add_one(x: int) -> int:\n    return x + 1\n";
        let opt = "def add_one(x: int) -> int:\n    return x + 2\n";
        let res = verify_functional_equivalence(orig, opt, "add_one");
        assert!(!res.verified);
        assert_eq!(res.smt_solver_status, "SAT");
        assert!(res.counterexample.is_some());
    }

    #[test]
    fn test_contract_verification_pass() {
        let code = "def abs_val(n: int) -> int:\n    \"\"\"\n    :requires: n >= 0\n    :ensures: result >= 0\n    \"\"\"\n    return n\n";
        let res = verify_contract_code(code);
        assert!(res.verified);
        assert_eq!(res.smt_solver_status, "UNSAT");
    }

    #[test]
    fn test_parallel_contracts_batch() {
        let json = r#"[
            {"name": "c1", "preconditions": ["x >= 0"], "postconditions": ["result >= 0"], "code": "def c1(x: int) -> int:\n    \"\"\"\n    :requires: x >= 0\n    :ensures: result >= 0\n    \"\"\"\n    return x\n"},
            {"name": "c2", "preconditions": ["x > 0"], "postconditions": ["result > 0"], "code": "def c2(x: int) -> int:\n    \"\"\"\n    :requires: x > 0\n    :ensures: result > 0\n    \"\"\"\n    return x + 1\n"}
        ]"#;
        let out = parallel::verify_contracts_parallel_str(json).unwrap();
        assert!(out.contains("\"verified\":true"));
        assert!(out.contains("\"smt_solver_status\":\"UNSAT\""));
        assert!(out.contains("\"solver_status\":\"UNSAT\""));
    }

    #[test]
    fn test_memory_safety_overflow() {
        let res = verify_memory_safety(i64::MAX, 1, i64::MAX);
        assert!(!res.verified);
        assert_eq!(res.smt_solver_status, "SAT");
    }

    #[test]
    fn test_parallel_contracts_violation_and_alias() {
        let json = r#"[
            {"function_name": "bad_dec", "preconditions": ["x > 0"], "postconditions": ["result < 0"], "code": "def bad_dec(x: int) -> int:\n    return x + 1"}
        ]"#;
        let out = parallel::verify_contracts_parallel_str(json).unwrap();
        assert!(out.contains("\"verified\":false"));
        assert!(out.contains("\"solver_status\":\"SAT\""));
    }
}
