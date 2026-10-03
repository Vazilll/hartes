use rayon::prelude::*;
use serde::{Deserialize, Serialize};

use crate::solver::{verify_contract_code, NativeVerificationResult};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContractSpecInput {
    #[serde(alias = "function_name")]
    pub name: Option<String>,
    #[serde(default)]
    pub preconditions: Vec<String>,
    #[serde(default)]
    pub postconditions: Vec<String>,
    #[serde(default)]
    pub code: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContractBatchOutput {
    pub name: String,
    pub verified: bool,
    pub smt_solver_status: String,
    pub solver_status: String,
    pub contract_satisfied: bool,
    pub proof_type: String,
    pub details: String,
}

pub fn verify_contracts_parallel_str(contracts_json: &str) -> Result<String, String> {
    let specs: Vec<ContractSpecInput> = match serde_json::from_str(contracts_json) {
        Ok(s) => s,
        Err(e) => return Err(format!("Invalid contracts JSON: {}", e)),
    };

    let outputs: Vec<ContractBatchOutput> = specs
        .into_par_iter()
        .map(|spec| {
            let name = spec.name.clone().unwrap_or_else(|| "unnamed_contract".to_string());
            let code_to_verify = if let Some(ref c) = spec.code {
                if !spec.preconditions.is_empty() || !spec.postconditions.is_empty() {
                    let mut header = String::new();
                    header.push_str("    \"\"\"\n");
                    for pre in &spec.preconditions {
                        header.push_str(&format!("    :requires: {}\n", pre));
                    }
                    for post in &spec.postconditions {
                        header.push_str(&format!("    :ensures: {}\n", post));
                    }
                    header.push_str("    \"\"\"\n");

                    let lines: Vec<&str> = c.lines().collect();
                    if !lines.is_empty() && lines[0].trim().starts_with("def ") {
                        let mut combined = String::new();
                        combined.push_str(lines[0]);
                        combined.push('\n');
                        combined.push_str(&header);
                        for l in &lines[1..] {
                            combined.push_str(l);
                            combined.push('\n');
                        }
                        combined
                    } else {
                        format!("{}\n{}", c, header)
                    }
                } else {
                    c.clone()
                }
            } else {
                let mut header = String::new();
                for pre in &spec.preconditions {
                    header.push_str(&format!("    :requires: {}\n", pre));
                }
                for post in &spec.postconditions {
                    header.push_str(&format!("    :ensures: {}\n", post));
                }
                format!("def {}(x: int) -> int:\n    \"\"\"\n{}\"\"\"\n    return x\n", name, header)
            };

            let res: NativeVerificationResult = verify_contract_code(&code_to_verify);

            ContractBatchOutput {
                name,
                verified: res.verified,
                smt_solver_status: res.smt_solver_status.clone(),
                solver_status: res.smt_solver_status.clone(),
                contract_satisfied: res.contract_satisfied,
                proof_type: res.proof_type,
                details: res.proof_details,
            }
        })
        .collect();

    serde_json::to_string(&outputs).map_err(|e| format!("Serialization error: {}", e))
}
