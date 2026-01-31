import json
import pathlib

# Load existing topics
path = pathlib.Path('c:/development/pitbula/quantivista/workflow_core/config/core_topics.json')
data = json.loads(path.read_text(encoding='utf-8'))

# Transform TopicResponsibilities
new_responsibilities = {}
for topic, roles in data['TopicResponsibilities'].items():
    if isinstance(roles, str):
        roles = [roles]
    
    # Default Context logic
    contexts = ["All"]
    if "Code" in topic or "Lint" in topic or "Complex" in topic:
        contexts = ["Code"]
    elif "Plan" in topic or "Goal" in topic or "Scope" in topic:
        contexts = ["Analysis", "Plan"]
    elif "Test" in topic or "Coverage" in topic:
        contexts = ["Code", "Plan"]
        
    new_responsibilities[topic] = {
        "Roles": roles,
        "Contexts": contexts
    }

data['TopicResponsibilities'] = new_responsibilities

# Save
path.write_text(json.dumps(data, indent=4), encoding='utf-8')
print("Successfully transformed core_topics.json")
