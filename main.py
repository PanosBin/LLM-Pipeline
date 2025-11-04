#main.py
import json
import argparse
import logging
from pathlib import Path
import os
import subprocess

# --- Imports ---
from src.parsers.parsing import TreeSitterParser
from src.clustering.clustering import cluster_methods_semantically
from src.summarizing.summarizer import LlamaSummarizer

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)-8s] --- %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = "/Users/panagiotisbinikos/Desktop/CB_Thesis/code/CB_N/out"
os.makedirs(OUTPUT_DIR, exist_ok=True)



# ============================
# 1. Scan with MobSF
# ============================
def scan_with_mobsf(source_folder: str) -> dict:
    logger.info(f"Running MobSF scan on: {source_folder}")
    temp_output = os.path.join(OUTPUT_DIR, "mobsf_temp.json")

    cmd = ["mobsfscan", "--json", "-o", temp_output, source_folder]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        logger.warning(f"MobSF returned non-zero exit code {result.returncode}, continuing anyway...")
    
    if not os.path.exists(temp_output):
        logger.error("MobSF scan produced no output file")
        return {"results": {}, "errors": []}

    with open(temp_output, "r") as f:
        results = json.load(f)

    filtered = {"results": {}, "errors": []}
    for vuln_name, vuln_data in results.get("results", {}).items():
        # Skip hardcoded_secret if you want only 15
        if vuln_name == "hardcoded_secret":
            continue
        
        java_files = [
            entry for entry in vuln_data.get("files", [])
            if entry.get("file_path", "").endswith(".java")
        ]
        if java_files:
            filtered["results"][vuln_name] = {
                "files": java_files,
                "metadata": vuln_data.get("metadata", {})
            }

    os.remove(temp_output)
    logger.info(f"MobSF scan complete. Found {len(filtered['results'])} vulnerability types.")
    return filtered 

# ============================
# 2. Parse codebase
# ============================
def parse_codebase(source_dir: str) -> list:
    logger.info(f"Parsing Java files in: '{source_dir}'")
    parser = TreeSitterParser()
    parsed_files = []
    for file_path in Path(source_dir).rglob("*.java"):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                source_code = f.read()
            java_file = parser.parse_java_file(source_code, str(file_path))
            if java_file and java_file.classes:
                parsed_files.append(java_file)
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}", exc_info=True)
    logger.info(f"Parsed {len(parsed_files)} Java files successfully.")
    return parsed_files

# ============================
# 3. Cluster methods
# ============================
def cluster_methods(parsed_files: list):
    logger.info("Starting semantic clustering of methods...")
    clusters, clusterer_obj = cluster_methods_semantically(parsed_files)
    logger.info(f"Generated {len(clusters)} clusters.")
    return clusters, clusterer_obj

# ============================
# 4. Identify vulnerable methods
# ============================


def is_position_within_method(mobsf_position, mobsf_lines, method_pos):
    if not method_pos:
        return False
    if mobsf_lines[0] == mobsf_lines[1]:  # single-line vulnerability
        if method_pos.start_line < mobsf_lines[0] < method_pos.end_line:
            return True
        elif method_pos.start_line == mobsf_lines[0] or method_pos.end_line == mobsf_lines[0]:
            return (method_pos.start_column <= mobsf_position[0] and 
                    method_pos.end_column >= mobsf_position[1])
    else:  # multi-line vulnerability
        if method_pos.start_line <= mobsf_lines[0] and method_pos.end_line >= mobsf_lines[1]:
            return True
        elif method_pos.start_line == mobsf_lines[0]:
            return method_pos.start_column <= mobsf_position[0]
    return False

def identify_vulnerable_methods(scan_results, parsed_files):
    """Maps vulnerabilities to specific methods and classes"""
    vulnerable_methods = []
    for result_key, vulnerability in scan_results.get("results", {}).items():
        for vuln_file in vulnerability.get("files", []):
            mobsf_path = vuln_file.get("file_path")
            relative_suffix = "/".join(mobsf_path.split("/")[-8:])
            
            for parsed_file in parsed_files:
                if relative_suffix in parsed_file.path or parsed_file.path.endswith(relative_suffix):
                    for java_class in parsed_file.classes:
                        for method in java_class.methods:
                            if is_position_within_method(
                                vuln_file.get("match_position", []),
                                vuln_file.get("match_lines", []),
                                method.position
                            ):
                                vulnerable_methods.append({
                                    "method": method,
                                    "class": java_class,
                                    "file": parsed_file,
                                    "vulnerability": result_key
                                })
    logger.info(f"Identified {len(vulnerable_methods)} vulnerable methods.")
    return vulnerable_methods

# ============================
# 5. Generate summaries
# ============================
def generate_summaries(clusters, vulnerable_methods):
    logger.info("Generating summaries for methods, classes, and clusters...")
    summarizer = LlamaSummarizer()
    summaries = {"clusters": {}, "classes": {}, "methods": {}}
    for idx, cluster in enumerate(clusters):
        summaries[f"cluster_{idx+1}"] = summarizer.summarize_cluster(cluster)
    for vuln_info in vulnerable_methods:
        method = vuln_info["method"]
        java_class = vuln_info["class"]
        method_key = f"{java_class.name}.{method.name}"
        if method_key not in summaries["methods"]:
            summaries["methods"][method_key] = summarizer.summarize_code(method.code)
        class_key = java_class.name
        if class_key not in summaries["classes"]:
            summaries["classes"][class_key] = summarizer.summarize_code(java_class.code)
    logger.info("Summaries generated.")
    return summaries

# ============================
# 6. Save outputs
# ============================
def save_outputs(scan_results, parsed_files, clusters, summaries):
    # 1. Scan results
    with open(os.path.join(OUTPUT_DIR, "mobsf_scan.json"), "w") as f:
        json.dump(scan_results, f, indent=2)
    logger.info("Saved scan results.")
    
    # 2. FULL Parsed files with all details
    def serialize_position(pos):
        return {
            "start_line": pos.start_line,
            "end_line": pos.end_line,
            "start_column": pos.start_column,
            "end_column": pos.end_column
        } if pos else None
    
    def serialize_method(method):
        return {
            "name": method.name,
            "return_type": method.return_type,
            "position": serialize_position(method.position),
            "code": method.code,
            "summary": method.summary,
            "cluster_summary": getattr(method, "cluster_summary", ""),
            "parent": None,  # avoid circular reference
            "parent_cluster": None,
            "is_false_positive": method.is_false_positive,
            "is_vulnerable": method.is_vulnerable,
            "vulnerability_metadata": method.vulnerability_meta,
            "vulnerability": method.vulnerability,
            "matched_string": method.matched_string,
            "parameters": [{"name": p.name, "type": p.type} for p in method.parameters]
        }
    
    def serialize_class(cls):
        return {
            "parent_file": None,  # avoid circular reference
            "name": cls.name,
            "position": serialize_position(cls.position),
            "code": cls.code,
            "summary": cls.summary,
            "methods": [serialize_method(m) for m in cls.methods]
        }
    
    def serialize_file(jfile):
        return {
            "path": jfile.path,
            "code": jfile.code,
            "classes": [serialize_class(c) for c in jfile.classes]
        }
    
    parsed_full = [serialize_file(pf) for pf in parsed_files]
    with open(os.path.join(OUTPUT_DIR, "parsed_files.json"), "w") as f:
        json.dump(parsed_full, f, indent=2)
    logger.info("Saved full parsed files.")
    
    # 3. Clusters
    clusters_data = []
    for idx, cluster in enumerate(clusters):
        # Flatten if nested lists detected
        if len(cluster) > 0 and isinstance(cluster[0], list):
            # flatten cluster
            flat_cluster = [method for sublist in cluster for method in sublist]
        else:
            flat_cluster = cluster
        
        clusters_data.append({
            "cluster_id": idx+1,
            "size": len(cluster),
            "methods": [
                {"name": m.name,
                 "class": getattr(m.parent, "name", "Unknown"),
                 "file": getattr(m.parent.parent_file, "path", "Unknown")}
                for m in cluster
            ]
        })
    with open(os.path.join(OUTPUT_DIR, "clusters.json"), "w") as f:
        json.dump(clusters_data, f, indent=2)
    logger.info("Saved clusters.")
    
    # 4. Summaries
    with open(os.path.join(OUTPUT_DIR, "summaries.json"), "w") as f:
        json.dump(summaries, f, indent=2)
    logger.info("Saved summaries.")

# ============================
# Main entry point
# ============================
def main():
    parser = argparse.ArgumentParser(description="Vulnerability analysis pipeline")
    parser.add_argument("--dir", type=str, required=True,
                        help="Android app source directory")
    parser.add_argument("--scan", action="store_true",
                        help="Run fresh MobSF scan (default: load existing)")
    parser.add_argument("--mobsf-output", type=str,
                        help="Path to existing MobSF scan JSON (if not scanning)")
    parser.add_argument("--no-summarize", action="store_true",
                        help="Skip summarization")
    args = parser.parse_args()


    # Scan or load
    if args.scan:
        scan_results = scan_with_mobsf(args.dir)
    elif args.mobsf_output:
        logger.info(f"Loading existing MobSF scan from: {args.mobsf_output}")
        with open(args.mobsf_output, "r") as f:
            scan_results = json.load(f)
    else:
        logger.error("Either --scan or --mobsf-output must be provided")
        return

    parsed_files = parse_codebase(args.dir)
    if not parsed_files:
        logger.warning("No Java files found. Exiting.")
        return

    clusters, clusterer_obj = cluster_methods_semantically(parsed_files)

    vulnerable_methods = identify_vulnerable_methods(scan_results, parsed_files)

    summaries = {"clusters": {}, "classes": {}, "methods": {}}
    if not args.no_summarize:
        summaries = generate_summaries(clusters, vulnerable_methods)


    save_outputs(scan_results, parsed_files, clusters, summaries)
    logger.info("Pipeline completed successfully.")

if __name__ == "__main__":
    main()
