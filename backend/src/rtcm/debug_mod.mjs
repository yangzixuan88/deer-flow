import * as m11 from '../domain/m11/mod.ts';
console.log('m11 exports with Interrupt:', Object.keys(m11).filter(k => k.includes('Interrupt') || k.includes('recordReal')));
