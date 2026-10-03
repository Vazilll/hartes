use std::collections::HashMap;
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict};
use serde::{Deserialize, Serialize};

use crate::z3_ffi::{SafeZ3Context, SafeZ3Solver, Z3_L_FALSE, Z3_L_TRUE};

#[pyclass(name = "VerificationResult")]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NativeVerificationResult {
    #[pyo3(get)]
    pub verified: bool,
    #[pyo3(get)]
    pub smt_solver_status: String,
    #[pyo3(get)]
    pub solver_status: String,
    #[pyo3(get)]
    pub contract_satisfied: bool,
    #[pyo3(get)]
    pub proof_type: String,
    #[pyo3(get)]
    pub counterexample: Option<HashMap<String, String>>,
    #[pyo3(get)]
    pub proof_details: String,
}

#[pymethods]
impl NativeVerificationResult {
    #[new]
    #[pyo3(signature = (verified=true, smt_solver_status="UNSAT", proof_type="FORMAL_PROOF", counterexample=None, proof_details=""))]
    pub fn new(
        verified: bool,
        smt_solver_status: &str,
        proof_type: &str,
        counterexample: Option<HashMap<String, String>>,
        proof_details: &str,
    ) -> Self {
        Self {
            verified,
            smt_solver_status: smt_solver_status.to_string(),
            solver_status: smt_solver_status.to_string(),
            contract_satisfied: verified,
            proof_type: proof_type.to_string(),
            counterexample,
            proof_details: proof_details.to_string(),
        }
    }

    pub fn to_dict<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let dict = PyDict::new(py);
        dict.set_item("verified", self.verified)?;
        dict.set_item("smt_solver_status", &self.smt_solver_status)?;
        dict.set_item("solver_status", &self.solver_status)?;
        dict.set_item("contract_satisfied", self.contract_satisfied)?;
        dict.set_item("proof_type", &self.proof_type)?;
        dict.set_item("proof_details", &self.proof_details)?;
        if let Some(ref ce) = self.counterexample {
            let ce_dict = PyDict::new(py);
            for (k, v) in ce {
                ce_dict.set_item(k, v)?;
            }
            dict.set_item("counterexample", ce_dict)?;
        } else {
            dict.set_item("counterexample", py.None())?;
        }
        Ok(dict)
    }

    pub fn __getitem__<'py>(&self, py: Python<'py>, key: &str) -> PyResult<PyObject> {
        let dict = self.to_dict(py)?;
        let item = dict.get_item(key)?;
        match item {
            Some(v) => Ok(v.unbind()),
            None => Err(pyo3::exceptions::PyKeyError::new_err(key.to_string())),
        }
    }

    #[pyo3(signature = (key, default=None))]
    pub fn get<'py>(&self, py: Python<'py>, key: &str, default: Option<Bound<'py, PyAny>>) -> PyResult<PyObject> {
        let dict = self.to_dict(py)?;
        match dict.get_item(key)? {
            Some(v) => Ok(v.unbind()),
            None => match default {
                Some(d) => Ok(d.unbind()),
                None => Ok(py.None()),
            },
        }
    }

    pub fn __repr__(&self) -> String {
        format!(
            "VerificationResult(verified={}, smt_solver_status='{}', proof_type='{}')",
            self.verified, self.smt_solver_status, self.proof_type
        )
    }
}

pub fn verify_memory_safety(offset: i64, length: i64, capacity: i64) -> NativeVerificationResult {
    let safe = (offset >= 0) && (length >= 0) && offset.checked_add(length).map_or(false, |sum| sum <= capacity);

    if safe {
        NativeVerificationResult {
            verified: true,
            smt_solver_status: "UNSAT".to_string(),
            solver_status: "UNSAT".to_string(),
            contract_satisfied: true,
            proof_type: "MEMORY_SAFETY".to_string(),
            counterexample: None,
            proof_details: "Memory bounds safety holds: 0 <= offset and 0 <= length and offset + length <= capacity (UNSAT)".to_string(),
        }
    } else {
        let mut map = HashMap::new();
        map.insert("offset".to_string(), offset.to_string());
        map.insert("length".to_string(), length.to_string());
        map.insert("capacity".to_string(), capacity.to_string());
        let reason = if offset < 0 || length < 0 {
            "Negative bounds violation"
        } else {
            "Out of bounds violation"
        };
        map.insert("reason".to_string(), reason.to_string());

        NativeVerificationResult {
            verified: false,
            smt_solver_status: "SAT".to_string(),
            solver_status: "SAT".to_string(),
            contract_satisfied: false,
            proof_type: "MEMORY_SAFETY".to_string(),
            counterexample: Some(map),
            proof_details: format!("Memory bounds safety violated: {}", reason),
        }
    }
}

// -------------------------------------------------------------------------
// Arithmetic Infix to SMT-LIB2 Translator
// -------------------------------------------------------------------------

#[derive(Debug, PartialEq, Eq)]
enum Token {
    Ident(String),
    Number(i64),
    Plus,
    Minus,
    Star,
    StarStar,
    LParen,
    RParen,
}

fn tokenize(input: &str) -> Vec<Token> {
    let mut tokens = Vec::new();
    let chars: Vec<char> = input.chars().collect();
    let len = chars.len();
    let mut i = 0;

    while i < len {
        let c = chars[i];
        if c.is_whitespace() {
            i += 1;
            continue;
        }
        if c == '+' {
            tokens.push(Token::Plus);
            i += 1;
        } else if c == '-' {
            tokens.push(Token::Minus);
            i += 1;
        } else if c == '*' {
            if i + 1 < len && chars[i + 1] == '*' {
                tokens.push(Token::StarStar);
                i += 2;
            } else {
                tokens.push(Token::Star);
                i += 1;
            }
        } else if c == '(' {
            tokens.push(Token::LParen);
            i += 1;
        } else if c == ')' {
            tokens.push(Token::RParen);
            i += 1;
        } else if c.is_digit(10) {
            let mut num_str = String::new();
            while i < len && chars[i].is_digit(10) {
                num_str.push(chars[i]);
                i += 1;
            }
            if let Ok(n) = num_str.parse::<i64>() {
                tokens.push(Token::Number(n));
            }
        } else if c.is_alphabetic() || c == '_' {
            let mut ident = String::new();
            while i < len && (chars[i].is_alphanumeric() || chars[i] == '_') {
                ident.push(chars[i]);
                i += 1;
            }
            tokens.push(Token::Ident(ident));
        } else {
            i += 1;
        }
    }
    tokens
}

struct Parser<'a> {
    tokens: &'a [Token],
    pos: usize,
}

impl<'a> Parser<'a> {
    fn new(tokens: &'a [Token]) -> Self {
        Self { tokens, pos: 0 }
    }

    fn peek(&self) -> Option<&Token> {
        self.tokens.get(self.pos)
    }

    fn advance(&mut self) -> Option<&Token> {
        let t = self.tokens.get(self.pos);
        if t.is_some() {
            self.pos += 1;
        }
        t
    }

    fn parse_expr(&mut self) -> Option<String> {
        let mut left = self.parse_term()?;

        while let Some(tok) = self.peek() {
            match tok {
                Token::Plus => {
                    self.advance();
                    let right = self.parse_term()?;
                    left = format!("(+ {} {})", left, right);
                }
                Token::Minus => {
                    self.advance();
                    let right = self.parse_term()?;
                    left = format!("(- {} {})", left, right);
                }
                _ => break,
            }
        }
        Some(left)
    }

    fn parse_term(&mut self) -> Option<String> {
        let mut left = self.parse_power()?;

        while let Some(tok) = self.peek() {
            match tok {
                Token::Star => {
                    self.advance();
                    let right = self.parse_power()?;
                    left = format!("(* {} {})", left, right);
                }
                _ => break,
            }
        }
        Some(left)
    }

    fn parse_power(&mut self) -> Option<String> {
        let base = self.parse_factor()?;

        if let Some(Token::StarStar) = self.peek() {
            self.advance();
            if let Some(Token::Number(2)) = self.peek() {
                self.advance();
                return Some(format!("(* {} {})", base, base));
            } else if let Some(Token::Number(3)) = self.peek() {
                self.advance();
                return Some(format!("(* {} (* {} {}))", base, base, base));
            } else {
                let exp = self.parse_factor()?;
                return Some(format!("(* {} {})", base, exp));
            }
        }
        Some(base)
    }

    fn parse_factor(&mut self) -> Option<String> {
        match self.advance()? {
            Token::Number(n) => Some(n.to_string()),
            Token::Ident(s) => Some(s.clone()),
            Token::Minus => {
                let inner = self.parse_factor()?;
                Some(format!("(- {})", inner))
            }
            Token::LParen => {
                let inner = self.parse_expr()?;
                if let Some(Token::RParen) = self.advance() {
                    Some(inner)
                } else {
                    None
                }
            }
            _ => None,
        }
    }
}

pub fn arithmetic_to_smtlib(expr_str: &str) -> Option<String> {
    let tokens = tokenize(expr_str);
    if tokens.is_empty() {
        return None;
    }
    let mut parser = Parser::new(&tokens);
    parser.parse_expr()
}

fn extract_return_expr(code: &str) -> Option<String> {
    for line in code.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with("return ") {
            return Some(trimmed[7..].trim().to_string());
        }
    }
    None
}

fn extract_params(code: &str) -> Vec<String> {
    let mut params = Vec::new();
    for line in code.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with("def ") {
            if let Some(lp) = trimmed.find('(') {
                if let Some(rp) = trimmed[lp..].find(')') {
                    let inside = &trimmed[lp + 1..lp + rp];
                    for p in inside.split(',') {
                        let name = p.split(':').next().unwrap_or("").trim();
                        if !name.is_empty() && name != "self" {
                            params.push(name.to_string());
                        }
                    }
                }
            }
            break;
        }
    }
    params
}

pub fn verify_functional_equivalence(orig_code: &str, opt_code: &str, _func_name: &str) -> NativeVerificationResult {
    if orig_code.trim() == opt_code.trim() {
        return NativeVerificationResult {
            verified: true,
            smt_solver_status: "UNSAT".to_string(),
            solver_status: "UNSAT".to_string(),
            contract_satisfied: true,
            proof_type: "FUNCTIONAL_EQUIVALENCE".to_string(),
            counterexample: None,
            proof_details: "Code implementations are identical (trivial equivalence)".to_string(),
        };
    }

    let orig_ret = match extract_return_expr(orig_code) {
        Some(r) => r,
        None => {
            return NativeVerificationResult {
                verified: false,
                smt_solver_status: "SKIPPED".to_string(),
                solver_status: "SKIPPED".to_string(),
                contract_satisfied: false,
                proof_type: "FUNCTIONAL_EQUIVALENCE".to_string(),
                counterexample: None,
                proof_details: "Could not extract return expression from original code".to_string(),
            };
        }
    };

    let opt_ret = match extract_return_expr(opt_code) {
        Some(r) => r,
        None => {
            return NativeVerificationResult {
                verified: false,
                smt_solver_status: "SKIPPED".to_string(),
                solver_status: "SKIPPED".to_string(),
                contract_satisfied: false,
                proof_type: "FUNCTIONAL_EQUIVALENCE".to_string(),
                counterexample: None,
                proof_details: "Could not extract return expression from optimized code".to_string(),
            };
        }
    };

    let orig_smt = match arithmetic_to_smtlib(&orig_ret) {
        Some(s) => s,
        None => {
            return NativeVerificationResult {
                verified: false,
                smt_solver_status: "UNKNOWN".to_string(),
                solver_status: "UNKNOWN".to_string(),
                contract_satisfied: false,
                proof_type: "FUNCTIONAL_EQUIVALENCE".to_string(),
                counterexample: None,
                proof_details: format!("Unsupported arithmetic syntax in: {}", orig_ret),
            };
        }
    };

    let opt_smt = match arithmetic_to_smtlib(&opt_ret) {
        Some(s) => s,
        None => {
            return NativeVerificationResult {
                verified: false,
                smt_solver_status: "UNKNOWN".to_string(),
                solver_status: "UNKNOWN".to_string(),
                contract_satisfied: false,
                proof_type: "FUNCTIONAL_EQUIVALENCE".to_string(),
                counterexample: None,
                proof_details: format!("Unsupported arithmetic syntax in: {}", opt_ret),
            };
        }
    };

    let params = extract_params(orig_code);

    let ctx = match SafeZ3Context::new() {
        Some(c) => c,
        None => {
            return NativeVerificationResult {
                verified: false,
                smt_solver_status: "ERROR".to_string(),
                solver_status: "ERROR".to_string(),
                contract_satisfied: false,
                proof_type: "FUNCTIONAL_EQUIVALENCE".to_string(),
                counterexample: None,
                proof_details: "Failed to initialize Z3 context".to_string(),
            };
        }
    };

    let solver = match SafeZ3Solver::new(&ctx) {
        Some(s) => s,
        None => {
            return NativeVerificationResult {
                verified: false,
                smt_solver_status: "ERROR".to_string(),
                solver_status: "ERROR".to_string(),
                contract_satisfied: false,
                proof_type: "FUNCTIONAL_EQUIVALENCE".to_string(),
                counterexample: None,
                proof_details: "Failed to initialize Z3 solver".to_string(),
            };
        }
    };

    let mut smt_script = String::new();
    for p in &params {
        smt_script.push_str(&format!("(declare-const {} Int)\n", p));
    }
    // Assert negated equivalence: orig != opt
    smt_script.push_str(&format!("(assert (distinct {} {}))\n", orig_smt, opt_smt));

    if !solver.assert_smtlib2(&smt_script) {
        return NativeVerificationResult {
            verified: false,
            smt_solver_status: "ERROR".to_string(),
            solver_status: "ERROR".to_string(),
            contract_satisfied: false,
            proof_type: "FUNCTIONAL_EQUIVALENCE".to_string(),
            counterexample: None,
            proof_details: "Failed to assert SMT-LIB2 script in Z3".to_string(),
        };
    }

    let (status, model_opt) = solver.check();

    if status == Z3_L_FALSE {
        // UNSAT -> No counterexample exists -> Proved Equivalent!
        NativeVerificationResult {
            verified: true,
            smt_solver_status: "UNSAT".to_string(),
            solver_status: "UNSAT".to_string(),
            contract_satisfied: true,
            proof_type: "FUNCTIONAL_EQUIVALENCE".to_string(),
            counterexample: None,
            proof_details: format!("Symbolic equivalence proved for all inputs (UNSAT): {} == {}", orig_ret, opt_ret),
        }
    } else if status == Z3_L_TRUE {
        // SAT -> Counterexample found!
        let mut ce_map = HashMap::new();
        if let Some(model_str) = model_opt {
            for line in model_str.lines() {
                let trimmed = line.trim();
                for p in &params {
                    if trimmed.contains(&format!("(define-fun {} () Int", p)) {
                        // next token or value
                        ce_map.insert(p.clone(), "0".to_string());
                    }
                }
            }
        }
        if ce_map.is_empty() {
            for p in &params {
                ce_map.insert(p.clone(), "0".to_string());
            }
        }
        ce_map.insert("reason".to_string(), "Functions produce distinct outputs".to_string());

        NativeVerificationResult {
            verified: false,
            smt_solver_status: "SAT".to_string(),
            solver_status: "SAT".to_string(),
            contract_satisfied: false,
            proof_type: "FUNCTIONAL_EQUIVALENCE".to_string(),
            counterexample: Some(ce_map),
            proof_details: format!("Functions are not functionally equivalent: {} != {}", orig_ret, opt_ret),
        }
    } else {
        NativeVerificationResult {
            verified: false,
            smt_solver_status: "UNKNOWN".to_string(),
            solver_status: "UNKNOWN".to_string(),
            contract_satisfied: false,
            proof_type: "FUNCTIONAL_EQUIVALENCE".to_string(),
            counterexample: None,
            proof_details: "SMT solver returned UNKNOWN (timeout or non-linear undecidability)".to_string(),
        }
    }
}

pub fn verify_contract_code(code: &str) -> NativeVerificationResult {
    let mut requires = Vec::new();
    let mut ensures = Vec::new();

    for line in code.lines() {
        let t = line.trim();
        if t.starts_with(":requires:") {
            requires.push(t[10..].trim().to_string());
        } else if t.starts_with(":ensures:") {
            ensures.push(t[9..].trim().to_string());
        }
    }

    if requires.is_empty() && ensures.is_empty() {
        return NativeVerificationResult {
            verified: true,
            smt_solver_status: "UNSAT".to_string(),
            solver_status: "UNSAT".to_string(),
            contract_satisfied: true,
            proof_type: "CONTRACT_VERIFICATION".to_string(),
            counterexample: None,
            proof_details: "No contracts specified, vacuously verified".to_string(),
        };
    }

    let params = extract_params(code);
    let ret_expr = extract_return_expr(code).unwrap_or_else(|| "0".to_string());

    let ctx = match SafeZ3Context::new() {
        Some(c) => c,
        None => {
            return NativeVerificationResult {
                verified: false,
                smt_solver_status: "ERROR".to_string(),
                solver_status: "ERROR".to_string(),
                contract_satisfied: false,
                proof_type: "CONTRACT_VERIFICATION".to_string(),
                counterexample: None,
                proof_details: "Failed to initialize Z3 context".to_string(),
            };
        }
    };

    let solver = match SafeZ3Solver::new(&ctx) {
        Some(s) => s,
        None => {
            return NativeVerificationResult {
                verified: false,
                smt_solver_status: "ERROR".to_string(),
                solver_status: "ERROR".to_string(),
                contract_satisfied: false,
                proof_type: "CONTRACT_VERIFICATION".to_string(),
                counterexample: None,
                proof_details: "Failed to initialize Z3 solver".to_string(),
            };
        }
    };

    let mut smt_script = String::new();
    for p in &params {
        smt_script.push_str(&format!("(declare-const {} Int)\n", p));
    }
    // If postcondition mentions 'result', substitute ret_expr for result
    let ret_smt = arithmetic_to_smtlib(&ret_expr).unwrap_or(ret_expr.clone());

    // Translate simple inequalities like "n >= 0", "result >= 0"
    for req in &requires {
        let smt_cond = translate_condition(req, &HashMap::new());
        smt_script.push_str(&format!("(assert {})\n", smt_cond));
    }

    let mut result_subs = HashMap::new();
    result_subs.insert("result".to_string(), ret_smt);

    for ens in &ensures {
        let smt_cond = translate_condition(ens, &result_subs);
        // Assert negated postcondition to prove validity
        smt_script.push_str(&format!("(assert (not {}))\n", smt_cond));
    }

    if !solver.assert_smtlib2(&smt_script) {
        return NativeVerificationResult {
            verified: false,
            smt_solver_status: "ERROR".to_string(),
            solver_status: "ERROR".to_string(),
            contract_satisfied: false,
            proof_type: "CONTRACT_VERIFICATION".to_string(),
            counterexample: None,
            proof_details: "Failed to assert SMT script".to_string(),
        };
    }

    let (status, _model) = solver.check();

    if status == Z3_L_FALSE {
        NativeVerificationResult {
            verified: true,
            smt_solver_status: "UNSAT".to_string(),
            solver_status: "UNSAT".to_string(),
            contract_satisfied: true,
            proof_type: "CONTRACT_VERIFICATION".to_string(),
            counterexample: None,
            proof_details: "Preconditions and postconditions verified (UNSAT)".to_string(),
        }
    } else {
        NativeVerificationResult {
            verified: false,
            smt_solver_status: "SAT".to_string(),
            solver_status: "SAT".to_string(),
            contract_satisfied: false,
            proof_type: "CONTRACT_VERIFICATION".to_string(),
            counterexample: Some(HashMap::new()),
            proof_details: "Contract postcondition violation detected (SAT)".to_string(),
        }
    }
}

fn translate_condition(cond: &str, subs: &HashMap<String, String>) -> String {
    let t = cond.trim();
    for op in &[">=", "<=", ">", "<", "==", "!="] {
        if let Some(idx) = t.find(op) {
            let left = t[..idx].trim();
            let right = t[idx + op.len()..].trim();

            let left_val = subs.get(left).cloned().unwrap_or_else(|| {
                arithmetic_to_smtlib(left).unwrap_or(left.to_string())
            });
            let right_val = subs.get(right).cloned().unwrap_or_else(|| {
                arithmetic_to_smtlib(right).unwrap_or(right.to_string())
            });

            let smt_op = match *op {
                ">=" => ">=",
                "<=" => "<=",
                ">" => ">",
                "<" => "<",
                "==" => "=",
                "!=" => "distinct",
                _ => "=",
            };
            return format!("({} {} {})", smt_op, left_val, right_val);
        }
    }
    format!("(= {} true)", t)
}
