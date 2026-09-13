type MessageCallback = (data: any) => void;

class WebSocketService {
  private ws: WebSocket | null = null;
  private url: string;
  private onMessageCallback: MessageCallback | null = null;
  private onStatusCallback: MessageCallback | null = null;

  constructor() {
    this.url = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8000/ws/analyze';
  }

  private speakerId: string | null = null;

  connect(onMessage: MessageCallback, onStatus?: MessageCallback, speakerId?: string) {
    this.onMessageCallback = onMessage;
    if (onStatus) this.onStatusCallback = onStatus;
    if (speakerId) this.speakerId = speakerId;
    
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      console.log('WebSocket connected to', this.url);
      this.sendStart();
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'status' && this.onStatusCallback) {
          this.onStatusCallback(data);
        } else if (this.onMessageCallback) {
          this.onMessageCallback(data);
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      if (this.onStatusCallback) {
          this.onStatusCallback({type: 'error', error});
      }
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
      if (this.onStatusCallback) {
          this.onStatusCallback({type: 'status', status: 'disconnected'});
      }
    };
  }
  
  sendStart() {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          const payload: any = { type: 'start' };
          if (this.speakerId) {
              payload.speaker_id = this.speakerId;
          }
          this.ws.send(JSON.stringify(payload));
      }
  }
  
  sendStop() {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          this.ws.send(JSON.stringify({type: 'stop'}));
      }
  }

  sendAudioChunk(chunk: Float32Array) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      // Send as binary buffer
      this.ws.send(chunk.buffer as ArrayBuffer);
    }
  }

  disconnect() {
    if (this.ws) {
      this.sendStop();
      this.ws.close();
      this.ws = null;
    }
  }
}

const wsService = new WebSocketService();
export default wsService;
