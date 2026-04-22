const fs = require('fs');
let code = fs.readFileSync('src/app/page.tsx', 'utf8');

const oldType = `type Message = {
  id: string;
  role: "user" | "agent";
  content: string;
};`;

const newType = `type Message = {
  id: string;
  role: "user" | "agent";
  content: string;
  finalContent?: string;
};`;

code = code.replace(oldType, newType);

const oldHistory = `        setMessages(data.messages.map((m: any) => ({
          id: uuidv4(),
          role: m.role,
          content: m.content
        })));`;

const newHistory = `        setMessages(data.messages.map((m: any) => ({
          id: uuidv4(),
          role: m.role,
          content: m.role === "agent" ? "" : m.content,
          finalContent: m.role === "agent" ? m.content : undefined
        })));`;

code = code.replace(oldHistory, newHistory);


const oldSSELoop = `          if (line.startsWith("data: ")) {
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
          }`;

const newSSELoop = `          if (line.startsWith("data: ")) {
            const dataStr = line.slice(6).trim();
            try {
              const data = JSON.parse(dataStr);
              if (data.text) {
                setMessages((prev) =>
                  prev.map((msg) => {
                    if (msg.id === agentMsgId) {
                      if (data.is_final) {
                        return { ...msg, finalContent: (msg.finalContent || "") + data.text };
                      } else {
                        return { ...msg, content: msg.content + data.text };
                      }
                    }
                    return msg;
                  })
                );
              }
            } catch (err) {}
          }`;

code = code.replace(oldSSELoop, newSSELoop);

const oldRender = `                    {/* Add whitespace-pre-wrap to properly render \\n newlines */}
                    <div className="flex-1 min-w-0 prose dark:prose-invert prose-p:leading-relaxed prose-p:my-1 text-black dark:text-white break-words whitespace-pre-wrap">
                      {msg.content || (msg.role === 'agent' && isTyping && idx === messages.length - 1 ? <span className="animate-pulse">...</span> : "")}
                    </div>`;

const newRender = `                    <div className="flex-1 min-w-0 break-words">
                      {msg.role === 'agent' && msg.content && (
                        <div className="text-gray-500 dark:text-gray-400 text-sm whitespace-pre-wrap font-mono mb-3 p-3 bg-gray-50 dark:bg-zinc-800/50 rounded-lg border border-gray-100 dark:border-zinc-800">
                          <div className="flex items-center gap-2 mb-2 text-[11px] font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300">
                            <span className="relative flex h-2 w-2">
                              {(!msg.finalContent && isTyping && idx === messages.length - 1) && (
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                              )}
                              <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
                            </span>
                            Processing
                            {(!msg.finalContent && isTyping && idx === messages.length - 1) ? "..." : " (Completed)"}
                          </div>
                          {msg.content}
                        </div>
                      )}
                      
                      {msg.role === 'agent' && msg.finalContent && (
                        <div className="prose dark:prose-invert prose-p:leading-relaxed prose-p:my-1 text-black dark:text-white whitespace-pre-wrap">
                          <div className="inline-flex items-center gap-1.5 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 text-xs px-2.5 py-1 rounded-md mb-2 font-medium border border-blue-100 dark:border-blue-800/30">
                            Result
                          </div>
                          <br />
                          {msg.finalContent}
                        </div>
                      )}

                      {msg.role === 'agent' && !msg.content && !msg.finalContent && isTyping && idx === messages.length - 1 && (
                        <span className="flex items-center gap-1 mt-2 text-gray-500">
                          <div className="h-2 w-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                          <div className="h-2 w-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                          <div className="h-2 w-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                        </span>
                      )}

                      {msg.role === 'user' && (
                        <div className="prose dark:prose-invert prose-p:leading-relaxed prose-p:my-1 text-black dark:text-white whitespace-pre-wrap">
                          {msg.content}
                        </div>
                      )}
                    </div>`;

code = code.replace(oldRender, newRender);

fs.writeFileSync('src/app/page.tsx', code);
console.log("Patched UI successfully");
