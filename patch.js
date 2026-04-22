const fs = require('fs');
let code = fs.readFileSync('frontend/src/app/page.tsx', 'utf8');

const oldFetchLoop = `      const reader = resp.body.getReader();
      const decoder = new TextDecoder("utf-8");

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\\n\\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const dataStr = line.slice(6).trim();
            if (dataStr === "[DONE]") {
              setIsTyping(false);
              break;
            }
            try {
              const data = JSON.parse(dataStr);
              if (data.content) {
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === agentMsgId
                      ? { ...msg, content: msg.content + data.content }
                      : msg
                  )
                );
              }
            } catch (err) {}
          }
        }
      }`;

const newFetchLoop = `      const reader = resp.body.getReader();
      const decoder = new TextDecoder("utf-8");
      
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\\n");
        buffer = lines.pop() || ""; // retain the last incomplete line

        for (let i = 0; i < lines.length; i++) {
          const line = lines[i];
          if (line.startsWith("event: agent.message.done") || line.startsWith("event: agent.workflow.failed")) {
             setIsTyping(false);
          }
          if (line.startsWith("data: ")) {
            const dataStr = line.slice(6).trim();
            try {
              const data = JSON.parse(dataStr);
              if (data.text) {
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === agentMsgId
                      ? { ...msg, content: msg.content + data.text }
                      : msg
                  )
                );
              }
            } catch (err) {}
          }
        }
      }`;

code = code.replace(oldFetchLoop, newFetchLoop);
fs.writeFileSync('frontend/src/app/page.tsx', code);
console.log("Patched successfully");
