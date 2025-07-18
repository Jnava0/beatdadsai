# File: backend/llm_provider.py
# Author: Gemini
# Date: July 17, 2024
# Description: Advanced, thread-safe provider for loading and managing
# multiple local Large Language Models (LLMs) with multi-backend support.

import yaml
import os
from threading import Lock
from typing import Dict, Any, Optional

# --- Import necessary LLM libraries ---
# We are importing these within a try-except block to handle cases where
# a user might not have all libraries installed, making the system more robust.
try:
    from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
    import torch
    HUGGINGFACE_AVAILABLE = True
except ImportError:
    HUGGINGFACE_AVAILABLE = False

try:
    from llama_cpp import Llama
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False

class LLMProvider:
    """
    A singleton class to manage the lifecycle of various LLMs.
    It dynamically loads models based on a configuration file, supports multiple
    backends (like HuggingFace and llama.cpp), and ensures that each model
    is loaded only once to conserve system resources (VRAM/RAM).
    """
    _instance = None
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        # The singleton pattern ensures that only one instance of LLMProvider exists.
        # This is crucial for managing a shared pool of resource-intensive models.
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_path: str = "config.yaml"):
        # The __init__ is only run the first time the instance is created.
        if not hasattr(self, 'initialized'):
            with self._lock:
                if not hasattr(self, 'initialized'):
                    print("Initializing LLMProvider...")
                    self.config_path = config_path
                    self.models_config = self._load_config()
                    self.loaded_models: Dict[str, Any] = {}
                    self.model_locks: Dict[str, Lock] = {model_id: Lock() for model_id in self.models_config}
                    self.initialized = True

    def _load_config(self) -> Dict[str, Any]:
        """Loads the model configurations from the YAML file."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found at: {self.config_path}")
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config.get("llm_models", {})

    def _load_huggingface_model(self, model_id: str):
        """Loads a model using the Hugging Face transformers library."""
        if not HUGGINGFACE_AVAILABLE:
            raise ImportError("Hugging Face 'transformers' or 'torch' library not installed.")
        
        model_config = self.models_config[model_id]
        model_path = model_config['model_path']
        config = model_config.get('config', {})
        precision = config.get('precision', 'float16')
        device_map = config.get('device_map', 'auto')

        print(f"Loading Hugging Face model '{model_id}' from {model_path}...")
        
        torch_dtype = getattr(torch, precision, torch.float16)

        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch_dtype,
            device_map=device_map,
        )
        tokenizer = AutoTokenizer.from_pretrained(model_path)

        # Create a text generation pipeline for easy interaction.
        pipe = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            torch_dtype=torch_dtype,
            device_map=device_map,
        )
        self.loaded_models[model_id] = pipe
        print(f"Model '{model_id}' loaded successfully.")

    def _load_llama_cpp_model(self, model_id: str):
        """Loads a GGUF model using the llama-cpp-python library."""
        if not LLAMA_CPP_AVAILABLE:
            raise ImportError("'llama-cpp-python' library not installed.")
            
        model_config = self.models_config[model_id]
        model_path = model_config['model_path']
        config = model_config.get('config', {})
        
        print(f"Loading GGUF model '{model_id}' from {model_path}...")

        # Pass config directly to the Llama constructor
        llm = Llama(
            model_path=model_path,
            n_gpu_layers=config.get('n_gpu_layers', 0),
            n_ctx=config.get('n_ctx', 2048),
            verbose=config.get('verbose', False)
        )
        self.loaded_models[model_id] = llm
        print(f"Model '{model_id}' loaded successfully.")

    def get_model(self, model_id: str) -> Any:
        """
        Retrieves a loaded model instance. If not loaded, it loads the model first.
        This method is thread-safe to prevent race conditions when multiple agents
        request the same model simultaneously.
        """
        if model_id not in self.models_config:
            raise ValueError(f"Model ID '{model_id}' not found in configuration.")

        # Use a model-specific lock to load the model.
        # This prevents other threads from trying to load the same model while it's
        # already in the process of being loaded.
        with self.model_locks[model_id]:
            if model_id not in self.loaded_models:
                provider = self.models_config[model_id].get("provider")
                if provider == "huggingface":
                    self._load_huggingface_model(model_id)
                elif provider == "llama-cpp":
                    self._load_llama_cpp_model(model_id)
                else:
                    raise ValueError(f"Unsupported provider '{provider}' for model '{model_id}'.")
        
        return self.loaded_models[model_id]

    def generate(self, model_id: str, prompt: str, max_tokens: int = 500, temperature: float = 0.7) -> str:
        """
        Generates text using the specified model.
        This provides a unified interface for agents, abstracting away the
        backend-specific generation calls.
        """
        model = self.get_model(model_id)
        provider = self.models_config[model_id].get("provider")

        print(f"Generating text with model '{model_id}'...")

        if provider == "huggingface":
            # The pipeline handles generation for Hugging Face models.
            sequences = model(prompt, max_new_tokens=max_tokens, do_sample=True, temperature=temperature, top_p=0.9)
            return sequences[0]['generated_text']
        
        elif provider == "llama-cpp":
            # The Llama object has a __call__ method for generation.
            output = model(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=["\n", "User:"] # Example stop sequences
            )
            return output['choices'][0]['text']
        
        else:
            raise ValueError(f"Generation not implemented for provider '{provider}'.")

# --- Example Usage (for testing) ---
if __name__ == '__main__':
    # This block demonstrates how to use the LLMProvider.
    # Note: You must update 'config.yaml' with the correct paths to your models.
    
    # Create an instance of the provider
    llm_provider = LLMProvider(config_path="config.yaml")

    # --- Test with a GGUF model ---
    try:
        gguf_model_id = 'qwen-7b-chat-gguf'
        print(f"\n--- Testing GGUF Model: {gguf_model_id} ---")
        response = llm_provider.generate(
            gguf_model_id,
            "User: Write a short story about a robot who discovers music.\nAssistant:",
            max_tokens=250
        )
        print("\nResponse:")
        print(response)
    except Exception as e:
        print(f"Could not test GGUF model: {e}")

    # --- Test with a Hugging Face model ---
    try:
        hf_model_id = 'llama2-7b-chat-hf'
        print(f"\n--- Testing Hugging Face Model: {hf_model_id} ---")
        response = llm_provider.generate(
            hf_model_id,
            "Write a python function that calculates the factorial of a number.",
            max_tokens=200
        )
        print("\nResponse:")
        print(response)
    except Exception as e:
        print(f"Could not test Hugging Face model: {e}")
