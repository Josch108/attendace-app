export function createSessionWebSocket(sessionId, onMessage, onStatusChange) {
  const wsUrl = `ws://localhost:8000/ws/class-sessions/${sessionId}`;
  const socket = new WebSocket(wsUrl);

  socket.onopen = () => {
    if (onStatusChange) onStatusChange("connected");
  };

  socket.onclose = () => {
    if (onStatusChange) onStatusChange("disconnected");
  };

  socket.onerror = (err) => {
    console.error("WebSocket error:", err);
    if (onStatusChange) onStatusChange("error");
  };

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (onMessage) onMessage(data);
    } catch (e) {
      console.error("Failed to parse WebSocket JSON:", e);
    }
  };

  return socket;
}
