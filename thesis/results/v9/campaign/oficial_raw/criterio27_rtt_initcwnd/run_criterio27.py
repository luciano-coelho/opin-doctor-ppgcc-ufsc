import sys, json
sys.path.insert(0, "/home/ec2-user/thesis/results/v9/campaign/scripts")
import orchestrator as orch
import dedicated_criteria as dc
import campaign_topology as ct

inventory = json.load(open("/home/ec2-user/inventory.json", encoding="utf-8"))
route_server = dict(ct.CAMPAIGN_ROUTE_SERVER)
executor = orch.SSHExecutor(inventory, key_path="/home/ec2-user/.ssh/campaign_key", route_server=route_server)

out_dir = __import__("pathlib").Path("/home/ec2-user/criterio27_out")

report = {}
try:
    report["criterio2"] = dc.run_criterio2_campaign(executor, out_dir)
except Exception as e:
    report["criterio2_error"] = f"{type(e).__name__}: {e}"

non_l0_routes = tuple(r for r in ct.CAMPAIGN_ROUTES if not r.startswith("L0-"))
try:
    report["criterio7"] = dc.run_criterio7(executor, out_dir, routes=non_l0_routes)
except Exception as e:
    report["criterio7_error"] = f"{type(e).__name__}: {e}"

print(json.dumps(report, indent=2, ensure_ascii=False))
