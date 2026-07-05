// Client-generated ids so editing never blocks on the server (docs §3.3).
import { customAlphabet } from "nanoid";

const nano = customAlphabet("abcdefghijklmnopqrstuvwxyz0123456789", 8);

export const newAgentId = () => `a_${nano()}`;
export const newDependencyId = () => `d_${nano()}`;
