import { redirect } from 'next/navigation';

export default function ProgramRootPage({ params }: { params: { programId: string } }) {
  redirect(`/programs/${params.programId}/overview`);
}
