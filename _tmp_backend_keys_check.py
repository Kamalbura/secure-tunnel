import ast
from pathlib import Path

root = Path("c:/Users/burak/ptojects/secure-tunnel")
models_path = root / "dashboard" / "backend" / "models.py"
source = models_path.read_text(encoding="utf-8")
module = ast.parse(source)

class_fields = {}
for node in module.body:
    if isinstance(node, ast.ClassDef):
        fields_list = []
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                fields_list.append((stmt.target.id, ast.get_source_segment(source, stmt.annotation) or ""))
        class_fields[node.name] = fields_list

def is_model(name):
    return name in class_fields and (name.endswith("Metrics") or name in {"ComprehensiveSuiteMetrics"})

def extract_type_name(ann: str):
    ann = ann.replace("Optional[", "").replace("]", "")
    ann = ann.replace("Field(", "")
    return ann.strip()

backend_keys = set()

def walk_model(prefix, class_name):
    for field_name, ann in class_fields.get(class_name, []):
        type_name = extract_type_name(ann)
        key = f"{prefix}.{field_name}" if prefix else field_name
        if is_model(type_name):
            walk_model(key, type_name)
        else:
            backend_keys.add(key)

walk_model("", "ComprehensiveSuiteMetrics")

print("backend_keys", len(backend_keys))
print("has_crypto_identity", "crypto_identity.kem_algorithm" in backend_keys)
print("has_run_context", "run_context.run_id" in backend_keys)
