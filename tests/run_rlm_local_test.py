import sys
import os
sys.path.insert(0, r"C:\vazus")
sys.path.insert(0, r"C:\vazus\scripts")
import os
import sys

# Force UTF-8 stdout/stderr to avoid Windows CP1251/CP866 rich library encoding issues
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from dotenv import load_dotenv

# Add rlm-mit directory to Python path if needed
sys.path.append(r"C:\vazus\rlm-mit")

from rlm import RLM
from rlm.logger import RLMLogger

load_dotenv()

def main():
    print("=" * 80)
    print("RUNNING RLM TEST VIA LOCAL OPENAI ADAPTER (AGY CLI)")
    print("=" * 80)

    # Load local adapter key
    key_path = r"C:\vazus\.adapter_key"
    adapter_key = "any_key_for_adapter"
    if os.path.exists(key_path):
        with open(key_path, "r") as f:
            adapter_key = f.read().strip()

    # Initialize RLM with OpenAI backend pointing to our local adapter
    rlm = RLM(
        backend="openai",
        backend_kwargs={
            "model_name": "openai:gemini-3.5-flash",
            "api_key": adapter_key,
            "base_url": "http://127.0.0.1:5001/v1",
        },
        environment="local",
        max_depth=2,
        max_iterations=3,
        logger=RLMLogger(log_dir="./logs"),
        verbose=True,
    )

    # Simple recursive reasoning prompt
    prompt = (
        "Solve this puzzle using python code in your REPL:\n"
        "1. Define a function is_prime(n).\n"
        "2. Call rlm_query() to ask: 'What are the first 3 prime numbers?'\n"
        "3. Verify those prime numbers using your is_prime function.\n"
        "4. Set answer['content'] to the verified list of primes and set answer['ready'] = True."
    )

    print(f"Prompt:\n{prompt}\n")
    print("Running RLM completion...")
    
    try:
        result = rlm.completion(prompt)
        print("\n" + "=" * 80)
        print("RLM EXECUTION COMPLETED")
        print("=" * 80)
        print(f"Response: {result.response}")
        print(f"Execution time: {result.execution_time:.2f}s")
    except Exception as e:
        print(f"Error during execution: {e}")

if __name__ == "__main__":
    main()
