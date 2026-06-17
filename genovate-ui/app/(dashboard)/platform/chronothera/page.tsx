import type { Metadata } from 'next';
import { ChronoTheraApp } from '@/components/chronothera/ChronoTheraApp';
export const metadata: Metadata = { title: 'ChronoThera internal module', robots: { index: false, follow: false } };
export default function ChronoTheraPage(){ return <ChronoTheraApp/>; }
