/**
 * AI Assistant Chat Component
 * 
 * Natural language interface for controlling Forge Lab
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  MessageSquare, Send, Bot, User, X,
  Sparkles, Zap, Loader2,
  Search, Scissors, Type, Music
} from 'lucide-react';
import { ENGINE_API_URL } from '@/lib/config';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  action?: AssistantAction;
}

interface AssistantAction {
  type: 'search' | 'trim' | 'generate_title' | 'add_music' | 'export' | 'navigate';
  params?: Record<string, any>;
  executed?: boolean;
}

interface AIChatProps {
  isOpen: boolean;
  onClose: () => void;
  projectId?: string;
  onAction?: (action: AssistantAction) => void;
}

// Quick action suggestions
const QUICK_ACTIONS = [
  { icon: Search, label: "Trouve un moment drôle", prompt: "Trouve-moi un moment drôle dans cette vidéo" },
  { icon: Type, label: "Génère des titres", prompt: "Génère 3 titres viraux pour ce clip" },
  { icon: Scissors, label: "Coupe les silences", prompt: "Active les jump cuts pour supprimer les silences" },
  { icon: Music, label: "Suggère une musique", prompt: "Quelle musique irait bien avec ce contenu?" },
];

export function AIChat({ isOpen, onClose, projectId, onAction }: AIChatProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: "Salut! Je suis ton assistant IA. Je peux t'aider à:\n\n• Trouver des moments spécifiques\n• Générer des titres et descriptions\n• Configurer les effets\n• Optimiser tes clips\n\nQu'est-ce que tu veux faire?",
      timestamp: new Date()
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  
  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);
  
  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      inputRef.current?.focus();
    }
  }, [isOpen]);
  
  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isLoading) return;
    
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: content.trim(),
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    
    try {
      // Call backend LLM API
      const response = await fetch(`${ENGINE_API_URL}/llm/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: content,
          project_id: projectId,
          context: messages.slice(-5).map(m => ({ role: m.role, content: m.content }))
        })
      });
      
      if (!response.ok) {
        throw new Error('LLM not available');
      }
      
      const data = await response.json();
      
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.response || "Désolé, je n'ai pas pu traiter ta demande.",
        timestamp: new Date(),
        action: data.action
      };
      
      setMessages(prev => [...prev, assistantMessage]);
      
      // Execute action if present
      if (data.action && onAction) {
        onAction(data.action);
      }
      
    } catch (error) {
      // Fallback response if LLM is not available
      const fallbackMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: getFallbackResponse(content),
        timestamp: new Date()
      };
      setMessages(prev => [...prev, fallbackMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [messages, projectId, onAction, isLoading]);
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(input);
  };
  
  const handleQuickAction = (prompt: string) => {
    setInput(prompt);
    sendMessage(prompt);
  };
  
  if (!isOpen) return null;
  
  return (
    <motion.div
      role="dialog"
      aria-modal="true"
      aria-labelledby="ai-chat-title"
      initial={{ opacity: 0, x: 300 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 300 }}
      className="fixed right-4 bottom-20 w-96 h-[600px] bg-gray-900 border border-gray-700
        rounded-2xl shadow-2xl flex flex-col overflow-hidden z-50"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-cyan-600/20 to-purple-600/20 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <div aria-hidden="true" className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-500 to-purple-500
            flex items-center justify-center">
            <Bot className="w-4 h-4 text-white" />
          </div>
          <div>
            <h3 id="ai-chat-title" className="font-semibold text-white">Forge Assistant</h3>
            <p className="text-xs text-gray-400">Powered by Ollama</p>
          </div>
        </div>
        <button
          onClick={onClose}
          aria-label="Fermer l’assistant"
          className="p-1 rounded hover:bg-gray-700 transition-colors"
        >
          <X aria-hidden="true" className="w-5 h-5 text-gray-400" />
        </button>
      </div>
      
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <AnimatePresence>
          {messages.map(message => (
            <motion.div
              key={message.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex gap-3 ${message.role === 'user' ? 'flex-row-reverse' : ''}`}
            >
              {/* Avatar */}
              <div aria-hidden="true" className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0
                ${message.role === 'user'
                  ? 'bg-cyan-600'
                  : 'bg-gradient-to-br from-purple-500 to-cyan-500'}`}
              >
                {message.role === 'user'
                  ? <User className="w-4 h-4 text-white" />
                  : <Sparkles className="w-4 h-4 text-white" />
                }
              </div>
              
              {/* Message content */}
              <div className={`max-w-[80%] rounded-2xl px-4 py-2 
                ${message.role === 'user'
                  ? 'bg-cyan-600 text-white rounded-tr-sm'
                  : 'bg-gray-800 text-gray-200 rounded-tl-sm'}`}
              >
                <p className="whitespace-pre-wrap text-sm">{message.content}</p>
                
                {/* Action indicator */}
                {message.action && (
                  <div className="mt-2 pt-2 border-t border-gray-700/50 flex items-center gap-2">
                    <Zap aria-hidden="true" className="w-3 h-3 text-amber-400" />
                    <span className="text-xs text-amber-400">
                      Action: {message.action.type}
                    </span>
                  </div>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        
        {/* Loading indicator */}
        {isLoading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex gap-3"
          >
            <div aria-hidden="true" className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-cyan-500
              flex items-center justify-center">
              <Loader2 className="w-4 h-4 text-white animate-spin" />
            </div>
            <div className="bg-gray-800 rounded-2xl rounded-tl-sm px-4 py-3">
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </motion.div>
        )}
        
        <div ref={messagesEndRef} />
      </div>
      
      {/* Quick actions */}
      <div className="px-4 py-2 border-t border-gray-800">
        <div className="flex gap-2 overflow-x-auto pb-2">
          {QUICK_ACTIONS.map((action, i) => (
            <button
              key={i}
              onClick={() => handleQuickAction(action.prompt)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 rounded-full 
                text-xs text-gray-300 hover:bg-gray-700 hover:text-white 
                transition-colors whitespace-nowrap"
            >
              <action.icon aria-hidden="true" className="w-3 h-3" />
              {action.label}
            </button>
          ))}
        </div>
      </div>
      
      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-gray-800">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Demande quelque chose..."
            aria-label="Message à l’assistant"
            className="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-2
              text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            aria-label="Envoyer le message"
            className="p-2 bg-cyan-600 rounded-xl hover:bg-cyan-500 transition-colors
              disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send aria-hidden="true" className="w-5 h-5 text-white" />
          </button>
        </div>
      </form>
    </motion.div>
  );
}

// Fallback responses when LLM is not available
function getFallbackResponse(input: string): string {
  const lower = input.toLowerCase();
  
  if (lower.includes('titre') || lower.includes('title')) {
    return "Pour générer des titres, assure-toi qu'Ollama est lancé avec un modèle comme llama3.2.\n\nEn attendant, voici des templates:\n• \"[RÉACTION] quand...\"\n• \"Il a VRAIMENT fait ça?!\"\n• \"Le moment où tout a changé...\"";
  }
  
  if (lower.includes('drôle') || lower.includes('funny') || lower.includes('moment')) {
    return "Je peux chercher des moments drôles en analysant les pics d'émotion et les rires détectés. Va dans l'onglet Segments et filtre par le tag 'humour' pour voir les moments les plus drôles.";
  }
  
  if (lower.includes('silence') || lower.includes('jump cut')) {
    return "Pour supprimer les silences:\n1. Va dans l'onglet 'Jump Cuts'\n2. Active l'option\n3. Choisis la sensibilité (Normal recommandé)\n4. Clique sur 'Analyser'\n\nL'export appliquera automatiquement les coupes.";
  }
  
  if (lower.includes('musique') || lower.includes('music')) {
    return "Pour ajouter de la musique:\n1. Va dans l'onglet 'Music'\n2. Clique sur 'Import'\n3. Sélectionne un fichier MP3\n4. Ajuste le volume et l'offset\n\nTip: Réduis le volume à 20-30% pour ne pas couvrir la voix.";
  }
  
  if (lower.includes('export')) {
    return "Pour exporter:\n1. Configure tes paramètres (sous-titres, intro, musique)\n2. Clique sur 'Export'\n3. Attends la fin du rendu\n4. Le fichier sera dans le dossier exports/\n\nTip: Active NVENC pour un export 5x plus rapide!";
  }
  
  return "Je suis l'assistant Forge Lab! Pour me parler, assure-toi qu'Ollama est lancé (ollama serve) avec un modèle installé.\n\nEn attendant, je peux répondre à des questions basiques sur l'utilisation de l'app.";
}

// Floating toggle button
export function AIChatToggle({ onClick, hasUnread }: { onClick: () => void; hasUnread?: boolean }) {
  return (
    <motion.button
      onClick={onClick}
      aria-label="Ouvrir l’assistant IA"
      className="fixed right-4 bottom-4 w-14 h-14 rounded-full
        bg-gradient-to-br from-cyan-500 to-purple-600
        shadow-lg shadow-cyan-500/20
        flex items-center justify-center
        hover:scale-105 transition-transform"
      whileHover={{ scale: 1.1 }}
      whileTap={{ scale: 0.95 }}
    >
      <MessageSquare aria-hidden="true" className="w-6 h-6 text-white" />
      {hasUnread && (
        <span aria-hidden="true" className="absolute top-0 right-0 w-3 h-3 bg-red-500 rounded-full" />
      )}
    </motion.button>
  );
}

export default AIChat;
