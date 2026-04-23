"use client"

import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Bot, User } from 'lucide-react';
import { apiFetch } from '@/lib/api';

interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
}

interface ChatInterfaceProps {
    documentId: string;
}

export default function ChatInterface({ documentId }: ChatInterfaceProps) {
    const [messages, setMessages] = useState<Message[]>([
        {
            id: '1',
            role: 'assistant',
            content: 'Initialize communication sequence. I am ready to contextualize and answer queries regarding your uploaded document.',
            timestamp: new Date(),
        }
    ]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || loading) return;

        const userMessage: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: input.trim(),
            timestamp: new Date(),
        };

        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setLoading(true);

        try {
            const response = await apiFetch<{
                success: boolean;
                query: string;
                answer: string;
                title: string;
            }>(`/api/ocr/query/${documentId}`, {
                method: 'POST',
                body: JSON.stringify({ query: userMessage.content }),
            });

            const aiMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: response.answer || 'Query processed, but no valid data generated. Please rephrase your input.',
                timestamp: new Date(),
            };
            setMessages(prev => [...prev, aiMessage]);
        } catch (error) {
            console.error('Error querying document:', error);
            const errorMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: 'Error encountered during NLP processing. Please try again.',
                timestamp: new Date(),
            };
            setMessages(prev => [...prev, errorMessage]);
        } finally {
            setLoading(false);
        }
    };

    const formatTime = (date: Date) => {
        return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    };

    return (
        <div className="h-full glass-card rounded-2xl flex flex-col overflow-hidden">
            {/* Chat Header */}
            <div className="p-5 border-b border-[#242c3a] bg-[#161b25]/80">
                <h2 className="text-lg font-bold text-[#f0f4f8] flex items-center gap-3 font-[var(--font-heading)]">
                    <div className="bg-[#29b6f6]/10 p-1.5 rounded-lg border border-[#29b6f6]/30 shadow-[0_0_10px_rgba(41,182,246,0.15)]">
                        <Bot size={20} className="text-[#29b6f6]" />
                    </div>
                    AI Query Agent
                </h2>
                <p className="text-[#6b7a8d] text-xs mt-2 font-[var(--font-mono)] uppercase tracking-widest">
                    Context-Aware Document Analysis
                </p>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-thin bg-[#0f1117]/40">
                {messages.map((message) => (
                    <div
                        key={message.id}
                        className={`flex gap-4 ${message.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-up`}
                    >
                        {message.role === 'assistant' && (
                            <div className="w-10 h-10 rounded-xl bg-[#1e2433] border border-[#242c3a] shadow-soft flex items-center justify-center shrink-0">
                                <Bot size={20} className="text-[#29b6f6]" />
                            </div>
                        )}

                        <div className={`flex flex-col gap-1.5 max-w-[75%] ${message.role === 'user' ? 'items-end' : 'items-start'}`}>
                            <div
                                className={`rounded-2xl px-5 py-3.5 ${message.role === 'user'
                                        ? 'bg-[#29b6f6] text-[#050a0e] shadow-[0_4px_20px_-4px_rgba(41,182,246,0.4)] font-medium rounded-tr-sm'
                                        : 'glass-card text-[#e8edf2] rounded-tl-sm'
                                    }`}
                            >
                                <p className="text-[15px] whitespace-pre-wrap leading-relaxed font-[var(--font-sans)]">{message.content}</p>
                            </div>
                            <span className="text-[10px] text-[#6b7a8d] font-[var(--font-mono)] px-1 uppercase tracking-widest">{formatTime(message.timestamp)}</span>
                        </div>

                        {message.role === 'user' && (
                            <div className="w-10 h-10 rounded-xl bg-[#29b6f6]/20 border border-[#29b6f6]/40 flex items-center justify-center shrink-0">
                                <User size={20} className="text-[#29b6f6]" />
                            </div>
                        )}
                    </div>
                ))}

                {loading && (
                    <div className="flex gap-4 justify-start animate-fade-up">
                        <div className="w-10 h-10 rounded-xl bg-[#1e2433] border border-[#242c3a] shadow-soft flex items-center justify-center shrink-0">
                            <Bot size={20} className="text-[#29b6f6]" />
                        </div>
                        <div className="glass-card rounded-2xl rounded-tl-sm px-6 py-4 flex items-center gap-3">
                            <Loader2 className="animate-spin text-[#29b6f6]" size={18} />
                            <span className="text-sm font-[var(--font-mono)] text-[#c9d1dc] tracking-wide uppercase">Processing</span>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} className="h-2" />
            </div>

            {/* Input Form */}
            <div className="p-5 border-t border-[#242c3a] bg-[#161b25]/90">
                <form onSubmit={handleSubmit} className="flex gap-3 max-w-4xl mx-auto relative">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Ask about this document..."
                        disabled={loading}
                        className="flex-1 pl-5 pr-12 py-3.5 bg-[#0f1117] border border-[#242c3a] text-[#f0f4f8] rounded-full focus:outline-none focus:ring-1 focus:ring-[#29b6f6] focus:border-[#29b6f6] text-[15px] disabled:opacity-50 disabled:cursor-not-allowed placeholder-[#6b7a8d] transition-all font-[var(--font-sans)] shadow-inner"
                    />
                    <button
                        type="submit"
                        disabled={!input.trim() || loading}
                        className="absolute right-2 top-2 bottom-2 bg-[#29b6f6] hover:bg-[#03a9f4] disabled:bg-[#242c3a] disabled:text-[#6b7a8d] text-[#050a0e] w-10 rounded-full transition-all flex items-center justify-center shadow-[0_0_15px_rgba(41,182,246,0.25)] disabled:shadow-none"
                    >
                        <Send size={18} className="ml-0.5" />
                    </button>
                </form>
            </div>
        </div>
    );
}