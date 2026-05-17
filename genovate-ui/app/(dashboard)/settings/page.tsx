'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { API_BASE_URL } from '@/lib/api/client';
import { useUIStore } from '@/lib/stores/ui-store';

export default function SettingsPage() {
  const theme = useUIStore((s) => s.theme);
  const setTheme = useUIStore((s) => s.setTheme);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Backend</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p>
            API URL: <span className="font-mono">{API_BASE_URL}</span>
          </p>
          <p className="text-xs text-muted-foreground">
            Configure via the <code>NEXT_PUBLIC_API_URL</code> environment variable.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Appearance</CardTitle>
        </CardHeader>
        <CardContent className="flex gap-2">
          {(['light', 'dark', 'system'] as const).map((t) => (
            <Button
              key={t}
              size="sm"
              variant={theme === t ? 'default' : 'outline'}
              onClick={() => setTheme(t)}
            >
              {t}
            </Button>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
