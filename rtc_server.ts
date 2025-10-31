import { Transport } from "@modelcontextprotocol/sdk/shared/transport.js";
import { JSONRPCMessage, MessageExtraInfo } from "@modelcontextprotocol/sdk/types.js";

// transport.ts
export class WebRTCTransport implements Transport {
    private readChannel: RTCDataChannel;
    private writeChannel: RTCDataChannel;
    private started = false;

    onclose?: () => void;
    onerror?: (error: Error) => void;
    onmessage?: (message: JSONRPCMessage, extra?: MessageExtraInfo) => void;
    sessionId?: string;
    setProtocolVersion?: (version: string) => void;

    constructor(readChannel: RTCDataChannel, writeChannel: RTCDataChannel) {
        this.readChannel = readChannel;
        this.writeChannel = writeChannel;
    }

    async start(): Promise<void> {
        if (this.started) return;
        this.started = true;

        // Handle incoming messages
        this.readChannel.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                if (this.onmessage) {
                    this.onmessage(message);
                }
            } catch (err) {
                console.error("[Transport] Failed to parse message:", err);
                this.onerror?.(err instanceof Error ? err : new Error(String(err)));
            }
        };

        // Handle close/error events
        this.readChannel.onclose = () => {
            this.onclose?.();
        };
        this.writeChannel.onclose = () => {
            this.onclose?.();
        };
        this.readChannel.onerror = (e) => {
            this.onerror?.(new Error(`readChannel error: ${e}`));
        };
        this.writeChannel.onerror = (e) => {
            this.onerror?.(new Error(`writeChannel error: ${e}`));
        };
    }

    async send(message: JSONRPCMessage): Promise<void> {
        if (this.writeChannel.readyState !== "open") {
            throw new Error("Transport write channel not open");
        }
        try {
            const json = JSON.stringify(message);
            this.writeChannel.send(json);
        } catch (err) {
            console.error("[Transport] Send error:", err);
            this.onerror?.(err instanceof Error ? err : new Error(String(err)));
        }
    }

    async close(): Promise<void> {
        try {
            this.readChannel.close();
            this.writeChannel.close();
        } catch (err) {
            console.error("[Transport] Close error:", err);
        } finally {
            this.onclose?.();
        }
    }
}
