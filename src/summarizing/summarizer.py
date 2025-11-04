from transformers import AutoTokenizer, AutoModelForCausalLM
import warnings
import torch

class LlamaSummarizer:
    def __init__(self, model_name="meta-llama/Llama-2-7b-chat-hf", device="cuda"):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name, device_map="auto", load_in_8bit=True
        )
        self.device = device
        self.context_size = 4096  # Model max context size

    def summarize_code(self, code: str, max_length=100):
        system_message = (
            "You are a professional Java code interpreter. Summarize the following code in ONE precise and concise sentence."
        )
        prompt = f"{system_message}\n\n``````"  # Fixed: added {code}
        
        tokens = self.tokenizer.encode(prompt)
        if len(tokens) > self.context_size:
            warnings.warn("Input too long for LLaMA model context. Skipping summarization.")
            return "Summary skipped: input too long."
        
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        outputs = self.model.generate(**inputs, max_new_tokens=max_length)
        summary = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return summary

    def summarize_cluster(self, cluster):
        code = "\n".join([method.code for method in cluster.get_elements()])
        return self.summarize_code(code)
