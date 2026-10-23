export const LIMITS: { encoded: number; json: number; ticks: number; inputs: number; first_tick: number; id: number; z: number };
export function boundedId(value: unknown, field: string, underscore?: boolean): string;
export function boundedTick(value: unknown, field?: string, max?: number): void;
export function boundedInputs(inputs: unknown, compact?: boolean, end?: number): void;
export function boundedJson(param: string, compressed?: boolean): Record<string, any>;
export function validateSubmission(s: any): void;
export function decodeChallenge(q: URLSearchParams): import('../play/share').SharedScore;
export function urlFieldError(params: URLSearchParams): string | null;
