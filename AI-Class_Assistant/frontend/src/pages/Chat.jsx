import React, { useEffect, useState } from "react";
import socket from "../sockets/socket";

export default function ChatPage({ user }) {
  const [messages, setMessages] = useState([]);

  useEffect(() => {
    socket.on("message", (data) => {
      setMessages((prev) => [...prev, data.msg]);
    });

    return () => socket.off("message");
  }, []);

  const sendMessage = () => {
    socket.emit("send_message", { msg: `Hi from ${user.name}` });
  };

  return (
    <div>
      <h1>Chat</h1>
      <button onClick={sendMessage}>Send Message</button>
      <ul>
        {messages.map((m, i) => (
          <li key={i}>{m}</li>
        ))}
      </ul>
    </div>
  );
}
