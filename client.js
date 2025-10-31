const { getServer } = require("./dist/mcp_instance.js");
const { WebRTCTransport } = require("./dist/rtc_server.js");

const pc = new RTCPeerConnection();

const textChannel = pc.createDataChannel("text");
const mcp_read = pc.createDataChannel("mcp_read");
const mcp_write = pc.createDataChannel("mcp_write");

mcp_read.onopen = () => console.log("[LOG] MCP read channel open");
mcp_read.onmessage = (e) => console.log("[MCP_READ]", e.data);

mcp_write.onmessage = (e) => console.log("[MCP_WRITE]", e.data);

// WebRTC signaling
const offer = await pc.createOffer();
await pc.setLocalDescription(offer);

const res = await fetch("http://localhost:8080/offer", {
  method: "POST",
  body: JSON.stringify({ sdp: offer.sdp, type: offer.type }),
  headers: { "Content-Type": "application/json" },
});
const answer = await res.json();
await pc.setRemoteDescription(answer);

console.log("[LOG] Remote SDP answer set.");

// Wait for channels to open
await Promise.all([
  new Promise((res) => mcp_read.onopen = res),
  new Promise((res) => mcp_write.onopen = res),
]);

const client = getServer();
console.log("Created MCP client", client);

const transport = new WebRTCTransport(textChannel, textChannel);
await transport.start();
await client.connect(transport);
console.log("Connected to backend via WebRTCTransport");
