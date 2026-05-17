import { redirect } from 'next/navigation';

export default async function ProgramRootPage({
  params,
}: {
  params: Promise<{ programId: string }>;
}) {
  const { programId } = await params;
  redirect(`/programs/${programId}/overview`);
}
