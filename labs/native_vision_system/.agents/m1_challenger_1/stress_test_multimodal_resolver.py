"""
Adversarial Stress Test Harness for MultimodalResolver
Location: C:\\vazus\\labs\\native_vision_system\\.agents\\m1_challenger_1\\stress_test_multimodal_resolver.py
"""

import sys
import os
import io
import time
import base64
import random
import traceback
import tempfile
import concurrent.futures
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Ensure vazus_core is importable
sys.path.insert(0, r"C:\vazus")

from PIL import Image

from vazus_core.multimodal_resolver import (
    MultimodalResolver,
    ResolvedMultimodalPayload,
    MultimodalResolverError,
    UnsupportedFormatError,
    ImageNotFoundError,
    ClipboardEmptyError,
    ArtifactNotFoundError,
    ClipboardAccessError,
    CorruptedImageError,
)

class StressTestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.findings: List[Dict[str, Any]] = []
        self.temp_dir = tempfile.TemporaryDirectory()

    def cleanup(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def log_result(self, test_name: str, status: str, details: str, expected: bool = True, vulnerability: bool = False):
        if status == "PASS":
            self.passed += 1
            print(f"[PASS] {test_name}: {details}")
        else:
            self.failed += 1
            print(f"[{'VULN' if vulnerability else 'FAIL'}] {test_name}: {details}")
            self.findings.append({
                "test": test_name,
                "status": status,
                "details": details,
                "vulnerability": vulnerability
            })

    def run_all(self):
        print("==================================================")
        print("STARTING ADVERSARIAL STRESS TEST HARNESS")
        print("==================================================")

        self.test_truncated_headers()
        self.test_corrupt_byte_payloads()
        self.test_synthetic_base64()
        self.test_at_references()
        self.test_type_safety_and_invalid_inputs()
        self.test_corrupted_idat_pixel_data_bypass()
        self.test_concurrent_image_resolution()
        self.test_resource_leaks_and_throughput()

        print("\n==================================================")
        print(f"SUMMARY: Passed={self.passed}, Failed={self.failed}, Findings={len(self.findings)}")
        print("==================================================")
        return self.findings

    # --- Test Category 1: Truncated Headers ---
    def test_truncated_headers(self):
        print("\n--- Category 1: Truncated Headers ---")
        
        truncated_cases = [
            ("PNG Magic Only (8b)", b"\x89PNG\r\n\x1a\n"),
            ("PNG Partial (4b)", b"\x89PNG"),
            ("PNG Truncated IHDR (16b)", b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00"),
            ("JPEG Magic Only (3b)", b"\xff\xd8\xff"),
            ("JPEG Partial (2b)", b"\xff\xd8"),
            ("WEBP Magic Only (12b)", b"RIFF\x00\x00\x00\x00WEBP"),
            ("WEBP Partial (4b)", b"RIFF"),
            ("GIF Header Only (6b)", b"GIF89a"),
            ("BMP Header Only (2b)", b"BM"),
            ("TIFF Header Only (4b)", b"II*\x00"),
        ]

        for name, payload in truncated_cases:
            try:
                res = MultimodalResolver.resolve(payload)
                # If resolve succeeds without exception, check if it's expected or a bug
                self.log_result(
                    f"TruncatedHeader_{name}",
                    "FAIL",
                    f"Resolved successfully without error! MIME: {res.mime_type}, size: {res.width}x{res.height}",
                    vulnerability=True
                )
            except (CorruptedImageError, UnsupportedFormatError) as e:
                self.log_result(
                    f"TruncatedHeader_{name}",
                    "PASS",
                    f"Correctly caught expected exception: {type(e).__name__} ('{e}')"
                )
            except Exception as e:
                self.log_result(
                    f"TruncatedHeader_{name}",
                    "FAIL",
                    f"Unhandled exception type {type(e).__name__}: '{e}'\n{traceback.format_exc()}",
                    vulnerability=False
                )

    # --- Category 2: Corrupt Byte Payloads ---
    def test_corrupt_byte_payloads(self):
        print("\n--- Category 2: Corrupt Byte Payloads ---")

        corrupt_cases = [
            ("Empty Bytes", b""),
            ("Random Garbage (1KB)", os.urandom(1024)),
            ("All Zeroes (1KB)", b"\x00" * 1024),
            ("All 0xFF (1KB)", b"\xff" * 1024),
            ("PNG Magic + Random Garbage", b"\x89PNG\r\n\x1a\n" + os.urandom(1000)),
            ("JPEG Magic + Random Garbage", b"\xff\xd8\xff" + os.urandom(1000)),
            ("WEBP Magic + Random Garbage", b"RIFF\xff\xff\xff\xffWEBP" + os.urandom(1000)),
        ]

        for name, payload in corrupt_cases:
            try:
                res = MultimodalResolver.resolve(payload)
                self.log_result(
                    f"CorruptBytes_{name}",
                    "FAIL",
                    f"Resolved successfully! MIME: {res.mime_type}, size: {res.width}x{res.height}",
                    vulnerability=True
                )
            except (CorruptedImageError, UnsupportedFormatError) as e:
                self.log_result(
                    f"CorruptBytes_{name}",
                    "PASS",
                    f"Correctly caught expected exception: {type(e).__name__} ('{e}')"
                )
            except Exception as e:
                self.log_result(
                    f"CorruptBytes_{name}",
                    "FAIL",
                    f"Unhandled exception type {type(e).__name__}: '{e}'\n{traceback.format_exc()}",
                    vulnerability=False
                )

    # --- Category 3: Synthetic Base64 Data ---
    def test_synthetic_base64(self):
        print("\n--- Category 3: Synthetic Base64 Data ---")

        # Create a valid 1x1 PNG image in bytes & base64
        buf = io.BytesIO()
        img_1x1 = Image.new("RGB", (1, 1), color="red")
        img_1x1.save(buf, format="PNG")
        png_1x1_bytes = buf.getvalue()
        b64_png = base64.b64encode(png_1x1_bytes).decode("utf-8")
        data_uri_png = f"data:image/png;base64,{b64_png}"

        # Test 3.1: Valid Base64 & Data URI
        try:
            res1 = MultimodalResolver.resolve(b64_png)
            self.log_result("SyntheticBase64_ValidRawB64", "PASS", f"Resolved {res1.width}x{res1.height} {res1.mime_type}")
        except Exception as e:
            self.log_result("SyntheticBase64_ValidRawB64", "FAIL", f"Failed on valid raw base64: {e}")

        try:
            res2 = MultimodalResolver.resolve(data_uri_png)
            self.log_result("SyntheticBase64_ValidDataURI", "PASS", f"Resolved {res2.width}x{res2.height} {res2.mime_type}")
        except Exception as e:
            self.log_result("SyntheticBase64_ValidDataURI", "FAIL", f"Failed on valid Data URI: {e}")

        # Test 3.2: Malformed Base64 / Non-Image Base64
        b64_non_image = base64.b64encode(b"Hello World this is plain text not an image").decode("utf-8")
        b64_text_data_uri = f"data:text/plain;base64,{b64_non_image}"
        b64_corrupt_uri = "data:image/png;base64,!!!INVALID_B64_CHARS!!!"
        b64_4char_valid_b64 = "ABCD"  # Decodes to 3 bytes b'\x00\x10\x83' (not a file, not image)
        nonexistent_filename = "nonexistent_image_12345.png"

        b64_negative_cases = [
            ("Text Base64 Data URI", b64_text_data_uri, (UnsupportedFormatError, CorruptedImageError, ImageNotFoundError)),
            ("Corrupt B64 Data URI", b64_corrupt_uri, (CorruptedImageError, UnsupportedFormatError, ImageNotFoundError)),
            ("Raw Non-Image B64 String", b64_non_image, (ImageNotFoundError, UnsupportedFormatError)),
            ("4-Char B64 'ABCD'", b64_4char_valid_b64, (ImageNotFoundError, UnsupportedFormatError)),
            ("Nonexistent Filename String", nonexistent_filename, (ImageNotFoundError, UnsupportedFormatError)),
        ]

        for name, payload, expected_errs in b64_negative_cases:
            try:
                res = MultimodalResolver.resolve(payload)
                self.log_result(
                    f"SyntheticBase64_{name}",
                    "FAIL",
                    f"Resolved successfully without error! MIME: {res.mime_type}, size: {res.width}x{res.height}",
                    vulnerability=True
                )
            except expected_errs as e:
                self.log_result(
                    f"SyntheticBase64_{name}",
                    "PASS",
                    f"Correctly caught expected exception: {type(e).__name__} ('{e}')"
                )
            except Exception as e:
                self.log_result(
                    f"SyntheticBase64_{name}",
                    "FAIL",
                    f"Unhandled exception type {type(e).__name__}: '{e}'\n{traceback.format_exc()}",
                    vulnerability=False
                )

    # --- Category 4: Symbolic @ References ---
    def test_at_references(self):
        print("\n--- Category 4: Symbolic @ References ---")

        # Create a temp test image in temp workspace
        temp_img_path = Path(self.temp_dir.name) / "test_artifact.png"
        img = Image.new("RGB", (10, 10), color="blue")
        img.save(temp_img_path, format="PNG")

        # Test @artifact resolution with explicit workspace_dir
        try:
            res = MultimodalResolver.resolve("@artifact:test_artifact.png", workspace_dir=self.temp_dir.name)
            self.log_result("@Ref_Artifact_Found", "PASS", f"Resolved artifact: {res.file_path}, {res.width}x{res.height}")
        except Exception as e:
            self.log_result("@Ref_Artifact_Found", "FAIL", f"Failed resolving valid artifact: {e}")

        # Test non-existent artifact
        try:
            res = MultimodalResolver.resolve("@artifact:nonexistent_xyz_9999.png", workspace_dir=self.temp_dir.name)
            self.log_result("@Ref_Artifact_NotFound", "FAIL", "Resolved non-existent artifact!", vulnerability=True)
        except ArtifactNotFoundError as e:
            self.log_result("@Ref_Artifact_NotFound", "PASS", f"Caught expected ArtifactNotFoundError: '{e}'")
        except Exception as e:
            self.log_result("@Ref_Artifact_NotFound", "FAIL", f"Unexpected exception: {type(e).__name__}: '{e}'")

        # Test @latest with explicit workspace_dir
        try:
            res = MultimodalResolver.resolve("@latest", workspace_dir=self.temp_dir.name)
            self.log_result("@Ref_Latest_Found", "PASS", f"Resolved latest image: {res.file_path}")
        except Exception as e:
            self.log_result("@Ref_Latest_Found", "FAIL", f"Failed resolving latest in temp dir: {e}")

    # --- Category 5: Type Safety & Invalid Inputs ---
    def test_type_safety_and_invalid_inputs(self):
        print("\n--- Category 5: Type Safety & Invalid Inputs ---")

        type_cases = [
            ("None Input", None, TypeError),
            ("Int Input (12345)", 12345, TypeError),
            ("List Input ([])", [], TypeError),
            ("Dict Input ({})", {}, TypeError),
            ("Empty String ('')", "", ValueError),
        ]

        for name, source_val, expected_type in type_cases:
            try:
                res = MultimodalResolver.resolve(source_val)
                self.log_result(f"TypeSafety_{name}", "FAIL", "Resolved invalid type input!", vulnerability=True)
            except expected_type as e:
                self.log_result(f"TypeSafety_{name}", "PASS", f"Caught expected {expected_type.__name__}: '{e}'")
            except Exception as e:
                self.log_result(f"TypeSafety_{name}", "FAIL", f"Unexpected exception type {type(e).__name__}: '{e}'")

    # --- Category 6: Corrupted IDAT Pixel Data Bypass Vulnerability Check ---
    def test_corrupted_idat_pixel_data_bypass(self):
        print("\n--- Category 6: Corrupted IDAT Pixel Data Bypass Check ---")

        # Build a valid 16x16 PNG
        buf = io.BytesIO()
        img_valid = Image.new("RGB", (16, 16), color="green")
        img_valid.save(buf, format="PNG")
        valid_png_bytes = buf.getvalue()

        # Corrupt the IDAT payload (replace the last 50% of the PNG bytes with random garbage or zeroes)
        cutoff = len(valid_png_bytes) // 2
        corrupted_png_bytes = valid_png_bytes[:cutoff] + (b"\x00" * (len(valid_png_bytes) - cutoff))

        try:
            res = MultimodalResolver.resolve(corrupted_png_bytes)
            # Check if Pillow can actually decode the pixel data of this resolved payload
            pixel_data_decoded = False
            try:
                with Image.open(io.BytesIO(res.raw_bytes)) as test_img:
                    test_img.load()  # Force reading pixel IDAT data
                pixel_data_decoded = True
            except Exception as load_err:
                pixel_data_decoded = False
                load_error_str = str(load_err)

            if not pixel_data_decoded:
                self.log_result(
                    "IDAT_Pixel_Corrupt_Bypass",
                    "FAIL",
                    f"MultimodalResolver.resolve() accepted corrupted PNG IDAT payload! Width/Height={res.width}x{res.height}, but Pillow img.load() fails with: '{load_error_str}'",
                    vulnerability=True
                )
            else:
                self.log_result("IDAT_Pixel_Corrupt_Bypass", "PASS", "Corrupted IDAT payload somehow loadable")
        except CorruptedImageError as e:
            self.log_result("IDAT_Pixel_Corrupt_Bypass", "PASS", f"Resolver rejected corrupted IDAT: '{e}'")
        except Exception as e:
            self.log_result("IDAT_Pixel_Corrupt_Bypass", "FAIL", f"Unexpected exception: {type(e).__name__}: '{e}'")

    # --- Category 7: Concurrent Image Resolution ---
    def test_concurrent_image_resolution(self):
        print("\n--- Category 7: Concurrent Image Resolution ---")

        # Prepare sample sources
        buf = io.BytesIO()
        img = Image.new("RGB", (32, 32), color="purple")
        img.save(buf, format="PNG")
        sample_bytes = buf.getvalue()
        sample_pil = Image.new("RGB", (16, 16), color="yellow")
        sample_file = Path(self.temp_dir.name) / "concurrent_sample.png"
        sample_pil.save(sample_file, format="PNG")

        sources = [
            sample_bytes,
            sample_pil,
            str(sample_file),
            f"data:image/png;base64,{base64.b64encode(sample_bytes).decode('utf-8')}",
            b"\x89PNG\r\n\x1a\nCORRUPTED_BYTES",
            "NONEXISTENT_FILE_XYZ.png"
        ]

        def worker_task(idx: int) -> Tuple[int, bool, str]:
            src = sources[idx % len(sources)]
            try:
                res = MultimodalResolver.resolve(src, workspace_dir=self.temp_dir.name)
                return (idx, True, f"Success {res.width}x{res.height}")
            except (CorruptedImageError, UnsupportedFormatError, ImageNotFoundError) as expected_e:
                return (idx, True, f"Expected catch: {type(expected_e).__name__}")
            except Exception as unhandled_e:
                return (idx, False, f"Unhandled exception {type(unhandled_e).__name__}: {unhandled_e}")

        total_requests = 300
        concurrency = 32
        successes = 0
        unhandled_errors = 0

        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(worker_task, i) for i in range(total_requests)]
            for future in concurrent.futures.as_completed(futures):
                idx, is_ok, msg = future.result()
                if is_ok:
                    successes += 1
                else:
                    unhandled_errors += 1
                    print(f"Concurrency Failure on task {idx}: {msg}")
        elapsed = time.time() - start_time

        if unhandled_errors == 0:
            self.log_result(
                "Concurrency_Stress",
                "PASS",
                f"Completed {total_requests} concurrent requests across {concurrency} threads in {elapsed:.3f}s ({total_requests/elapsed:.1f} req/s). 0 unhandled errors."
            )
        else:
            self.log_result(
                "Concurrency_Stress",
                "FAIL",
                f"Encountered {unhandled_errors} unhandled errors during concurrent resolution!",
                vulnerability=True
            )

    # --- Category 8: Resource Leaks and Throughput ---
    def test_resource_leaks_and_throughput(self):
        print("\n--- Category 8: Resource Leaks and Throughput ---")

        buf = io.BytesIO()
        img = Image.new("RGB", (64, 64), color="orange")
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        iterations = 2000
        start_time = time.time()
        for _ in range(iterations):
            payload = MultimodalResolver.resolve(png_bytes)
            _ = payload.to_inline_data_dict()
            _ = payload.to_dict()
            _ = payload.sha256

        elapsed = time.time() - start_time
        ops_per_sec = iterations / elapsed
        self.log_result(
            "Throughput_Benchmark",
            "PASS",
            f"Processed {iterations} image resolutions in {elapsed:.3f}s ({ops_per_sec:.1f} ops/sec)"
        )


if __name__ == "__main__":
    runner = StressTestRunner()
    try:
        findings = runner.run_all()
    finally:
        runner.cleanup()
