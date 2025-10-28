# pip install transformers torch lightning peft torchmetrics
from huggingface_hub import hf_hub_download
from torch import no_grad, sigmoid
import importlib.util
import sys

repo_id = "ZivK/smollm2-end-of-sentence"
model_name = "token_model.ckpt"
model_src_name = "model.py"
checkpoint_path = hf_hub_download(repo_id=repo_id, filename=model_name)
model_src_path = hf_hub_download(repo_id=repo_id, filename=model_src_name)

# Load the model source code, you can also just download model.py
spec = importlib.util.spec_from_file_location("SmolLM", model_src_path)
smollm_model = importlib.util.module_from_spec(spec)
sys.modules["smollm_model"] = smollm_model
spec.loader.exec_module(smollm_model)

device = "cpu"  # for GPU usage or "cpu" for CPU usage
label_map = {0: "Incomplete", 1: "Complete"}
model = smollm_model.SmolLM.load_from_checkpoint(checkpoint_path).to(device)
inputs = model.tokenizer("Tu vas bien?", return_tensors="pt").to(device)
model.eval()
with no_grad():
    logits = model(inputs)
    probs = sigmoid(logits)
    prediction = (probs > 0.5).int().item()
    label = label_map[prediction]
    conf = probs.item() if probs.item() > 0.5 else 1 - probs.item()
print(f"Sentence is {label}, Confidence: {conf * 100}%")
