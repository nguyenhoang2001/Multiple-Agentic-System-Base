"use client";

import { useState, useRef, useEffect } from "react";
import { v4 as uuidv4 } from "uuid";
import { Plus, Send, Menu, KeySquare, Settings, Cpu, Trash2 } from "lucide-react";

type Message = {
  id: string;
  role: "user" | "agent";
  content: string;
  finalContent?: string;
  startTime?: number;
  responseTime?: number;
};

type SessionInfo = {
  id: string;
  title: string;
  updatedAt: number;
};

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Load sessions from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem("chat_sessions");
    if (saved) {
      try {
        setSessions(JSON.parse(saved).sort((a: SessionInfo, b: SessionInfo) => b.updatedAt - a.updatedAt));
      } catch(e) {}
    }
  }, []);

  // Save sessions to localStorage when updated
  useEffect(() => {
    localStorage.setItem("chat_sessions", JSON.stringify(sessions));
  }, [sessions]);

  // Auto-scroll
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isTyping]);

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  };

  const createNewChat = () => {
    setCurrentSessionId(null);
    setMessages([]);
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  const loadSession = async (sessionId: string) => {
    setCurrentSessionId(sessionId);
    setMessages([]);
    try {
      const res = await fetch(`http://localhost:8000/api/v1/sessions/${sessionId}/history?user_id=default-user`);
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages.map((m: any) => ({
          id: uuidv4(),
          role: m.role === 'assistant' ? 'agent' : m.role,
          content: m.role === 'assistant' ? '' : m.content,
          finalContent: m.role === 'assistant' ? m.content : undefined
        })));
      } else {
        // Handle 404 or errors
        setMessages([]);
      }
    } catch(err) {
      console.error(err);
    }
  };

  const deleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    try {
      await fetch(`http://localhost:8000/api/v1/sessions/${sessionId}?user_id=default-user`, {
        method: "DELETE"
      });
    } catch(err) {}
    setSessions(prev => prev.filter(s => s.id !== sessionId));
    if (currentSessionId === sessionId) {
      createNewChat();
    }
  };

  const handleSend = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || isTyping) return;

    let activeSessionId = currentSessionId;
    if (!activeSessionId) {
      activeSessionId = uuidv4();
      setCurrentSessionId(activeSessionId);
      const newSession: SessionInfo = {
        id: activeSessionId,
        title: input.trim().slice(0, 30) + "...",
        updatedAt: Date.now()
      };
      setSessions(prev => [newSession, ...prev]);
    } else {
      // Update session timestamp
      setSessions(prev => {
        const list = [...prev];
        const idx = list.findIndex(s => s.id === activeSessionId);
        if (idx !== -1) list[idx].updatedAt = Date.now();
        return list.sort((a,b) => b.updatedAt - a.updatedAt);
      });
    }

    const userMsg: Message = { id: uuidv4(), role: "user", content: input.trim() };
    const agentMsgId = uuidv4();
    
    setMessages((prev) => [...prev, userMsg, { id: agentMsgId, role: "agent", content: "", startTime: Date.now() }]);
    setInput("");
    setIsTyping(true);

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    try {
      const resp = await fetch(`http://localhost:8000/api/v1/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: activeSessionId,
          user_id: "default-user",
          message: userMsg.content,
        }),
      });

      if (!resp.body) throw new Error("No response body");

      const reader = resp.body.getReader();
      const decoder = new TextDecoder("utf-8");
      
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; // retain the last incomplete line

        for (let i = 0; i < lines.length; i++) {
          const line = lines[i];
          if (line.startsWith("event: agent.message.done") || line.startsWith("event: agent.workflow.failed")) {
             setIsTyping(false);
             setMessages((prev) =>
               prev.map((msg) => {
                 if (msg.id === agentMsgId && msg.startTime && !msg.responseTime) {
                   return { ...msg, responseTime: (Date.now() - msg.startTime) / 1000 };
                 }
                 return msg;
               })
             );
          }
          if (line.startsWith("data: ")) {
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
          }
        }
      }
    } catch (error) {
      console.error(error);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === agentMsgId
            ? { ...msg, content: "Đã có lỗi xảy ra. Không thể kết nối tới server." }
            : msg
        )
      );
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex h-screen w-full bg-white dark:bg-[#212121] text-gray-800 dark:text-gray-100 font-sans text-[15px] overflow-hidden">
      
      {/* Sidebar */}
      <div className={`${isSidebarOpen ? 'flex' : 'hidden'} md:flex flex-col w-[260px] flex-shrink-0 bg-[#f9f9f9] dark:bg-[#171717] h-full transition-all duration-300`}>
        <div className="flex flex-col h-full w-full px-3 py-3">
          <button 
            onClick={createNewChat} 
            className="flex items-center gap-3 w-full h-10 px-3 py-2 rounded-lg hover:bg-gray-200 dark:hover:bg-zinc-800 transition-colors text-sm font-medium"
          >
            <div className="flex items-center justify-center bg-white dark:bg-zinc-800 border border-gray-200 dark:border-zinc-700 shadow-sm w-7 h-7 rounded-full">
              <Plus className="w-4 h-4" />
            </div>
            New Chat
            <KeySquare className="w-4 h-4 ml-auto text-gray-400" />
          </button>

          <div className="flex-1 overflow-y-auto mt-4 px-1 custom-scrollbar">
            <div className="text-xs font-semibold text-gray-500 dark:text-gray-400 mb-2 px-2 tracking-wide">History Chat</div>
            {sessions.map(session => (
              <div 
                key={session.id} 
                className={`group flex items-center w-full px-2 py-2 rounded-lg cursor-pointer ${currentSessionId === session.id ? 'bg-gray-200 dark:bg-zinc-800' : 'hover:bg-gray-200 dark:hover:bg-zinc-800'}`}
                onClick={() => loadSession(session.id)}
              >
                <div className="flex-1 text-left truncate text-sm">
                  {session.title}
                </div>
                <button 
                  onClick={(e) => deleteSession(e, session.id)} 
                  className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-500 transition-opacity"
                >
                  <Trash2 className="w-4 h-4 text-gray-500 hover:text-red-500" />
                </button>
              </div>
            ))}
          </div>

          <div className="mt-auto border-t border-gray-200 dark:border-zinc-800 pt-2">
            <button className="flex items-center gap-2 w-full px-2 py-3 hover:bg-gray-200 dark:hover:bg-zinc-800 rounded-lg text-sm transition-colors">
              <div className="w-8 h-8 rounded-full bg-gradient-to-r from-purple-400 to-blue-500 flex items-center justify-center text-white font-bold text-xs shadow-sm">
                US
              </div>
              <span className="font-medium truncate">Huytai102</span>
              <Settings className="w-4 h-4 ml-auto text-gray-500" />
            </button>
          </div>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex flex-col flex-1 h-full min-w-0 bg-white dark:bg-[#212121] relative">
        {/* Header */}
        <header className="sticky top-0 z-10 flex items-center p-3 text-gray-800 dark:text-gray-200 bg-white/80 dark:bg-[#212121]/80 backdrop-blur-md">
          <button 
            onClick={() => setIsSidebarOpen(!isSidebarOpen)} 
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-zinc-800 md:hidden"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="font-semibold text-lg flex items-center gap-2 ml-2 cursor-pointer hover:bg-gray-100 dark:hover:bg-zinc-800 px-3 py-1.5 rounded-lg transition-colors">
            gemma4:e2b <span className="text-gray-400 text-sm">▼</span>
          </div>
        </header>

        {/* Messages / Scrollable area */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto custom-scrollbar w-full flex flex-col items-center pb-4">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full min-h-[50vh] px-4 w-full max-w-3xl">
              <div className="w-16 h-16 bg-white dark:bg-zinc-800 dark:border dark:border-zinc-700 shadow-md rounded-full flex items-center justify-center mb-6">
                <Cpu className="w-8 h-8 text-black dark:text-white" />
              </div>
              <h1 className="text-3xl font-semibold mb-8 text-black dark:text-white text-center">How can I help you today?</h1>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full text-center">
                 {/* Gợi ý */}
              </div>
            </div>
          ) : (
            <div className="w-full flex flex-col">
              {messages.map((msg, idx) => (
                <div key={idx} className={`w-full py-6 px-4 flex justify-center ${msg.role === 'agent' ? 'bg-[#f4f4f4] dark:bg-[#2f2f2f]' : ''}`}>
                  <div className="flex gap-4 w-full max-w-3xl">
                    <div className="flex-shrink-0">
                      {msg.role === 'user' ? (
                        <div className="w-8 h-8 rounded bg-gradient-to-r from-purple-400 to-blue-500 flex items-center justify-center text-white font-bold text-xs shadow-sm">
                          US
                        </div>
                      ) : (
                        <div className="w-8 h-8 rounded bg-[#10a37f] flex items-center justify-center text-white shadow-sm">
                          <Cpu className="w-5 h-5" />
                        </div>
                      )}
                    </div>
                    <div className="flex-1 min-w-0 break-words">
                      {msg.role === 'agent' && msg.content && (
                        <div className="text-gray-500 dark:text-gray-400 text-sm whitespace-pre-wrap mb-3 p-3 bg-gray-50 dark:bg-zinc-800/50 rounded-lg border border-gray-100 dark:border-zinc-800">
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
                          <div className="flex items-center gap-2 mb-2">
                            <div className="inline-flex items-center gap-1.5 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 text-xs px-2.5 py-1 rounded-md font-medium border border-blue-100 dark:border-blue-800/30">
                              Result
                            </div>
                            {msg.responseTime && (
                              <span className="text-xs text-gray-500 dark:text-gray-400 font-mono">
                                {msg.responseTime.toFixed(1)}s
                              </span>
                            )}
                          </div>
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
                    </div>
                  </div>
                </div>
              ))}
              {/* Padding for sticky bottom area */}
              <div className="h-32 w-full flex-shrink-0"></div>
            </div>
          )}
        </div>

        {/* Input Box Footer */}
        <div className="absolute bottom-0 left-0 right-0 pt-4 pb-6 bg-gradient-to-t from-white via-white to-transparent dark:from-[#212121] dark:via-[#212121]">
          <div className="w-full max-w-3xl mx-auto px-4">
            <div className="relative flex w-full flex-col shadow-[0_0_15px_rgba(0,0,0,0.1)] dark:shadow-[0_0_15px_rgba(0,0,0,0.2)] bg-white dark:bg-[#2f2f2f] rounded-[24px] overflow-hidden border border-gray-200 dark:border-zinc-700">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={handleInput}
                onKeyDown={handleKeyDown}
                placeholder="Message gemma4:e2b..."
                className="w-full max-h-[200px] bg-transparent resize-none py-4 px-4 pr-12 text-[16px] outline-none text-black dark:text-white dark:placeholder-gray-400"
                rows={1}
                style={{ minHeight: '56px' }}
              />
              <div className="absolute right-2 bottom-2">
                <button
                  onClick={handleSend}
                  disabled={!input.trim() || isTyping}
                  className={`p-2 rounded-xl transition-colors flex items-center justify-center ${
                    input.trim() && !isTyping 
                      ? 'bg-black text-white dark:bg-white dark:text-black hover:opacity-80' 
                      : 'bg-gray-100 text-gray-400 dark:bg-zinc-700 dark:text-zinc-500 cursor-not-allowed'
                  }`}
                >
                  <Send className="w-4 h-4" strokeWidth={2.5} />
                </button>
              </div>
            </div>
            <div className="text-center text-xs text-gray-500 dark:text-gray-400 mt-3 font-normal">
              Agents can make mistakes. Consider verifying important information.
            </div>
          </div>
        </div>

      </div>

      <style dangerouslySetInnerHTML={{__html: `
        .custom-scrollbar::-webkit-scrollbar {
          width: 6px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background-color: rgba(156, 163, 175, 0.3);
          border-radius: 20px;
        }
        .dark .custom-scrollbar::-webkit-scrollbar-thumb {
          background-color: rgba(156, 163, 175, 0.15);
        }
      `}} />
    </div>
  );
}
