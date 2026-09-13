from app.ml.model import model_instance

def get_model_status():
    return "loaded" if model_instance.is_loaded else "not loaded"

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
        
    return result
