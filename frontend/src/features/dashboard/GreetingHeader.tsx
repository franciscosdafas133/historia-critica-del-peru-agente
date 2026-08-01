function getTimeOfDayGreeting(): string {
  const hour = new Date().getHours()
  if (hour < 12) return 'Buenos días'
  if (hour < 19) return 'Buenas tardes'
  return 'Buenas noches'
}

export function GreetingHeader({ firstName }: { firstName: string }) {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight text-ink-900">
        {getTimeOfDayGreeting()}, {firstName}
      </h1>
      <p className="mt-1 text-sm text-ink-500">Aquí está el resumen de tu semana de estudio.</p>
    </div>
  )
}
