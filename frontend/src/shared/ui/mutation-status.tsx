type MutationStatusProps = {
  pending?: boolean;
  success?: string | null;
  error?: string | null;
};

export function MutationStatus({
  pending,
  success,
  error,
}: MutationStatusProps) {
  if (error) {
    return (
      <div className="rounded-2xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-red-100">
        {error}
      </div>
    );
  }

  if (pending) {
    return (
      <div className="rounded-2xl border border-cyan-300/25 bg-cyan-300/10 px-4 py-3 text-sm text-cyan-100">
        Operation en cours...
      </div>
    );
  }

  if (success) {
    return (
      <div className="rounded-2xl border border-emerald-300/25 bg-emerald-300/10 px-4 py-3 text-sm text-emerald-100">
        {success}
      </div>
    );
  }

  return null;
}
