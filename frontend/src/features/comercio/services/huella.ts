/**
 * Huella del dispositivo para el modelo de fraude. Usa FNV-1a y no crypto.subtle porque esta última
 * solo existe en contextos seguros (HTTPS o localhost).
 */
export function fnv1a(texto: string): string {
  let hash = 0x811c9dc5;
  for (let i = 0; i < texto.length; i++) {
    hash ^= texto.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(16).padStart(8, '0');
}

export function calcularHuella(): string {
  return fnv1a(
    [
      navigator.userAgent,
      navigator.language,
      navigator.hardwareConcurrency,
      `${screen.width}x${screen.height}x${screen.colorDepth}`,
      Intl.DateTimeFormat().resolvedOptions().timeZone,
      new Date().getTimezoneOffset(),
    ].join('|'),
  );
}
