from app.ml.model import model_instance

def get_model_status():
    return {
        "status": "loaded" if model_instance.is_loaded else "not loaded",
        "model_status": getattr(model_instance, "model_status", "UNKNOWN"),
        "production_ready": getattr(model_instance, "production_ready", False),
        "validation_status": getattr(model_instance, "validation_status", "NOT_VALIDATED"),
        "disclaimer": getattr(model_instance, "model_disclaimer", "Anti-spoofing model is not validated for production use.")
    }

def run_inference(audio_data: bytes):
    if not model_instance.is_loaded:
        return {
            "status": "error",
            "message": "V-SHIELD ML model is not loaded"
        }
    
    result = model_instance.predict(audio_data)
    
    if "error" in result:
        return {
            "status": "error",
            "message": result["error"]
        }
        
    result["model_status"] = getattr(model_instance, "model_status", "UNKNOWN")
    result["production_ready"] = getattr(model_instance, "production_ready", False)
    result["disclaimer"] = getattr(model_instance, "model_disclaimer", "Anti-spoofing model is not validated for production use.")
    return result
