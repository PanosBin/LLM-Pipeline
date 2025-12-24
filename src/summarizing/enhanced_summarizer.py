"""
Enhanced summarizer with method call analysis.
Supervisor requirement: Analyze what methods a class uses to create more specific summaries.
"""
import re
import logging
from typing import List, Set
from transformers import AutoTokenizer, AutoModelForCausalLM
import warnings
import torch

logger = logging.getLogger(__name__)


class EnhancedLlamaSummarizer:
    """
    Enhanced summarizer that analyzes method calls within classes
    to generate more specific and contextual summaries.
    """

    def __init__(self, model_name="meta-llama/Llama-2-7b-chat-hf", device="cuda"):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name, device_map="auto", load_in_8bit=True
        )
        self.device = device
        self.context_size = 4096  # Model max context size

    def extract_method_calls(self, code: str) -> Set[str]:
        """
        Extract method calls from Java code.
        Returns a set of method names that are called in the code.
        """
        # Pattern to match method calls: word followed by opening parenthesis
        # Excludes: if, for, while, switch (control flow keywords)
        pattern = r'\b(?!if|for|while|switch|catch)([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
        matches = re.findall(pattern, code)

        # Filter out common Java keywords and constructors (capitalized)
        filtered = set()
        for match in matches:
            # Skip if it's a constructor (starts with capital letter)
            if match[0].isupper():
                continue
            # Skip common keywords
            if match in ['new', 'return', 'throw', 'assert', 'synchronized']:
                continue
            filtered.add(match)

        return filtered

    def extract_class_dependencies(self, code: str) -> Set[str]:
        """
        Extract class dependencies (types used in the code).
        """
        # Pattern to match class names (typically PascalCase)
        pattern = r'\b([A-Z][a-zA-Z0-9_]*)\b'
        matches = re.findall(pattern, code)

        # Filter out common Java types
        common_types = {'String', 'Integer', 'Boolean', 'Long', 'Double', 'Float',
                       'List', 'Map', 'Set', 'ArrayList', 'HashMap', 'HashSet',
                       'Object', 'Class', 'System', 'Exception', 'Override',
                       'View', 'Context', 'Bundle', 'Intent'}

        filtered = set(m for m in matches if m not in common_types)
        return filtered

    def summarize_code(self, code: str, max_length=100):
        """Basic code summarization without context."""
        system_message = (
            "You are a professional Java code interpreter. "
            "Summarize the following code in ONE precise and concise sentence."
        )
        prompt = f"{system_message}\n\nCode:\n```java\n{code}\n```"

        tokens = self.tokenizer.encode(prompt)
        if len(tokens) > self.context_size:
            warnings.warn("Input too long for LLaMA model context. Skipping summarization.")
            return "Summary skipped: input too long."

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        outputs = self.model.generate(**inputs, max_new_tokens=max_length)
        summary = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Extract only the generated summary (remove prompt)
        if "```" in summary:
            summary = summary.split("```")[-1].strip()

        return summary

    def summarize_class_with_context(self, java_class, max_length=150):
        """
        Enhanced class summarization that includes method call analysis.
        This makes the summary more specific by understanding what the class does.
        """
        code = java_class.code
        class_name = java_class.name

        # Extract method calls and dependencies
        method_calls = self.extract_method_calls(code)
        dependencies = self.extract_class_dependencies(code)

        # Get method names defined in this class
        method_names = [m.name for m in java_class.methods]

        logger.info(f"Analyzing class '{class_name}':")
        logger.info(f"  - Methods: {', '.join(method_names[:5])}...")
        logger.info(f"  - Calls: {', '.join(list(method_calls)[:5])}...")
        logger.info(f"  - Dependencies: {', '.join(list(dependencies)[:5])}...")

        # Create context-aware prompt
        context_info = []
        if method_calls:
            context_info.append(f"Calls methods: {', '.join(list(method_calls)[:10])}")
        if dependencies:
            context_info.append(f"Uses classes: {', '.join(list(dependencies)[:10])}")
        if method_names:
            context_info.append(f"Defines methods: {', '.join(method_names[:5])}")

        context_str = "; ".join(context_info) if context_info else "No additional context"

        system_message = (
            f"You are a professional Java code interpreter. "
            f"Analyze this class and provide ONE precise, concise sentence describing its PURPOSE and FUNCTIONALITY.\n"
            f"Context: {context_str}"
        )

        # Truncate code if too long to fit in context
        max_code_length = 2000  # chars
        code_snippet = code[:max_code_length] if len(code) > max_code_length else code

        prompt = f"{system_message}\n\nClass name: {class_name}\n\nCode:\n```java\n{code_snippet}\n```"

        tokens = self.tokenizer.encode(prompt)
        if len(tokens) > self.context_size:
            logger.warning(f"Class '{class_name}' code too long, using basic summarization")
            return self.summarize_code(code, max_length)

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        outputs = self.model.generate(**inputs, max_new_tokens=max_length)
        summary = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Extract only the generated summary (remove prompt)
        if "```" in summary:
            summary = summary.split("```")[-1].strip()

        return summary

    def summarize_cluster(self, cluster, max_length=200):
        """
        Summarize a cluster of classes.
        Provides overview of what the clustered classes collectively do.
        """
        if not cluster:
            return "Empty cluster"

        # Collect all class names
        class_names = [cls.name for cls in cluster]

        # Collect method calls across all classes
        all_method_calls = set()
        all_dependencies = set()

        for cls in cluster:
            all_method_calls.update(self.extract_method_calls(cls.code))
            all_dependencies.update(self.extract_class_dependencies(cls.code))

        logger.info(f"Analyzing cluster with {len(cluster)} classes:")
        logger.info(f"  - Classes: {', '.join(class_names[:5])}...")
        logger.info(f"  - Common calls: {', '.join(list(all_method_calls)[:10])}...")
        logger.info(f"  - Common dependencies: {', '.join(list(all_dependencies)[:10])}...")

        # Create cluster context
        context_info = []
        context_info.append(f"Contains {len(cluster)} classes: {', '.join(class_names[:5])}")
        if all_method_calls:
            context_info.append(f"Common methods called: {', '.join(list(all_method_calls)[:10])}")
        if all_dependencies:
            context_info.append(f"Common dependencies: {', '.join(list(all_dependencies)[:10])}")

        context_str = "; ".join(context_info)

        system_message = (
            f"You are a professional Java code interpreter. "
            f"These classes are semantically clustered together. "
            f"Provide ONE concise sentence describing the COMMON PURPOSE or FUNCTIONALITY of this cluster.\n"
            f"Context: {context_str}"
        )

        # Combine code from all classes (truncated)
        combined_code = "\n\n".join([f"// Class: {cls.name}\n{cls.code[:500]}" for cls in cluster[:3]])

        prompt = f"{system_message}\n\nCluster code sample:\n```java\n{combined_code}\n```"

        tokens = self.tokenizer.encode(prompt)
        if len(tokens) > self.context_size:
            logger.warning("Cluster code too long, using simplified summary")
            return f"Cluster of {len(cluster)} classes: {', '.join(class_names[:5])}"

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        outputs = self.model.generate(**inputs, max_new_tokens=max_length)
        summary = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Extract only the generated summary
        if "```" in summary:
            summary = summary.split("```")[-1].strip()

        return summary
