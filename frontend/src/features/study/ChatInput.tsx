import { useState, useRef } from 'react'
import type { KeyboardEvent } from 'react'
import { SendHorizontal } from 'lucide-react'
import { IconButton } from '@/components/ui/IconButton'

interface ChatInputProps {
  onSubmit: (value: string) => void
  placeholder?: string
  disabled?: boolean
}

export function ChatInput({ onSubmit, placeholder = 'Escribe tu pregunta…', disabled = false }: ChatInputProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  function handleSubmit() {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSubmit(trimmed)
    setValue('')
    textareaRef.current?.focus()
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="flex items-end gap-2 rounded-xl border border-surface-300 bg-surface-50 p-2 shadow-soft focus-within:border-brand-400">
      <label htmlFor="chat-input" className="sr-only">
        Escribe tu mensaje para el tutor
      </label>
      <textarea
        id="chat-input"
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        rows={1}
        disabled={disabled}
        className="max-h-32 min-h-[2.5rem] flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-ink-900 placeholder:text-ink-300 focus:outline-none disabled:opacity-60"
      />
      <IconButton
        icon={<SendHorizontal className="h-4 w-4" />}
        label="Enviar mensaje"
        onClick={handleSubmit}
        disabled={disabled || !value.trim()}
        variant="solid"
        className="bg-tutor-500 text-white hover:bg-tutor-600 disabled:hover:bg-tutor-500"
      />
    </div>
  )
}
