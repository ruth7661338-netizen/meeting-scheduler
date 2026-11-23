"""יוצר את הדאטהסט ב-LangSmith (פעם אחת)."""
import truststore
truststore.inject_into_ssl()

from dotenv import load_dotenv
from langsmith import Client

from scheduler.dataset_examples import build_examples

load_dotenv()
DATASET_NAME = "meeting-scheduler"

client = Client()
if client.has_dataset(dataset_name=DATASET_NAME):
    print(f"Dataset '{DATASET_NAME}' already exists - skipping.")
else:
    ds = client.create_dataset(
        dataset_name=DATASET_NAME,
        description="בקשות לקביעת פגישות בעברית + אילוצים נכונים + האם קיים מועד",
    )
    examples = build_examples()
    client.create_examples(
        dataset_id=ds.id,
        inputs=[e["inputs"] for e in examples],
        outputs=[e["outputs"] for e in examples],
    )
    print(f"Created '{DATASET_NAME}' with {len(examples)} examples.")