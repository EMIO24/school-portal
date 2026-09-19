const { TextDecoder, TextEncoder } = require('util');
if (!global.TextEncoder) global.TextEncoder = TextEncoder;
if (!global.TextDecoder) global.TextDecoder = TextDecoder;
import '@testing-library/jest-dom';
if (!global.crypto) Object.defineProperty(global, 'crypto', {value: {randomUUID: () => 'test-notification-request-key'}, configurable:true});
if (!global.crypto.randomUUID) global.crypto.randomUUID = () => 'test-notification-request-key';

