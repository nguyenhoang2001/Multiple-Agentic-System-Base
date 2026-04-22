const fs = require('fs');
let code = fs.readFileSync('frontend/src/app/page.tsx', 'utf8');

const oldLine = `        setMessages(data.messages.map((m: Message) => ({
          id: uuidv4(),
          role: m.role,
          content: m.content
        })));`;

const newLine = `        setMessages(data.messages.map((m: any) => ({
          id: uuidv4(),
          role: m.role === 'assistant' ? 'agent' : m.role,
          content: m.role === 'assistant' ? '' : m.content,
          finalContent: m.role === 'assistant' ? m.content : undefined
        })));`;

code = code.replace(oldLine, newLine);
fs.writeFileSync('frontend/src/app/page.tsx', code);
