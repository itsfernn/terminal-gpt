def get_completion(model: dict):
    provider = model.get("provider", None)
    if provider == "openai":
        from models.openai import complete as openai_complete
        return openai_complete
    else:
        raise ValueError(f"Unsupported provider: {provider}")

