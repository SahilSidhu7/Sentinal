export function FaqCard({ question, answer }: { question: string; answer: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 transition-transform duration-200 ease-out hover:scale-[1.02]">
      <h3 className="text-base font-semibold text-white">{question}</h3>
      <p className="mt-2 text-sm leading-relaxed text-slate-400">{answer}</p>
    </div>
  );
}
