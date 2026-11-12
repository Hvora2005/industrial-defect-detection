import { useEffect, useRef, useState } from "react";
import type { Detection } from "../types";
export function useMonitor(receive: (data: Detection) => void) {
  const receiver = useRef(receive);
  receiver.current = receive;
  const [connected, setConnected] = useState(false);
  useEffect(() => {
    let disposed = false;
    let socket: WebSocket;
    let timer: number;
    function connect() {
      socket = new WebSocket(
        `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/monitor`,
      );
      socket.onopen = () => {
        if (!disposed) setConnected(true);
      };
      socket.onmessage = (event) => {
        try {
          const result: unknown = JSON.parse(String(event.data));
          if (
            result &&
            typeof result === "object" &&
            "defects" in result &&
            Array.isArray(result.defects) &&
            "status" in result
          )
            receiver.current(result as Detection);
        } catch {
          /* Invalid event is not an inspection. */
        }
      };
      socket.onerror = () => socket.close();
      socket.onclose = () => {
        if (!disposed) {
          setConnected(false);
          timer = window.setTimeout(connect, 2000);
        }
      };
    }
    connect();
    return () => {
      disposed = true;
      window.clearTimeout(timer);
      socket.close();
    };
  }, []);
  return connected;
}
