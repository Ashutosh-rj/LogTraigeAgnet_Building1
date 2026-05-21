import tiktoken
from typing import List, Dict

class SlidingWindowChunker:
    def __init__(self, chunk_size: int = 200, overlap: int = 200):
        self.chunk_size = chunk_size
        self.overlap = overlap
        # tiktoken requires the package to be installed
        self.encoding = tiktoken.get_encoding("cl100k_base")

    def chunk_logs(self, raw_logs: List[Dict]) -> List[Dict]:
        """
        Transforms multi-GB logs into overlapping token windows.
        Ensures cross-boundary context is never lost.
        """
        chunks = []
        current_chunk = []
        current_tokens = 0
        chunk_idx = 0

        for log in raw_logs:
            # log format is typically expected to have timestamp, level, service, message
            log_str = f"[{log.get('timestamp', log.get('observed_at', ''))}] {log.get('level', '')} {log.get('source', log.get('service', ''))} - {log.get('message', '')}"
            tokens = len(self.encoding.encode(log_str))
            
            # Context overflow mitigation: truncate individual log entries > 500 tokens
            if tokens > 500:
                encoded = self.encoding.encode(log_str)[:500]
                log_str = self.encoding.decode(encoded) + "... [TRUNCATED]"
                tokens = 500

            if current_tokens + tokens > self.chunk_size and current_chunk:
                # Save chunk
                start_time = current_chunk[0].get('timestamp', current_chunk[0].get('observed_at'))
                end_time = current_chunk[-1].get('timestamp', current_chunk[-1].get('observed_at'))
                chunks.append({
                    "chunk_index": chunk_idx,
                    "logs": current_chunk.copy(),
                    "start_time": start_time,
                    "end_time": end_time
                })
                chunk_idx += 1

                # Apply sliding window (keep last N logs fitting 'overlap' tokens)
                overlap_tokens = 0
                overlap_chunk = []
                for prev_log in reversed(current_chunk):
                    prev_log_str = f"[{prev_log.get('timestamp', prev_log.get('observed_at', ''))}] {prev_log.get('level', '')} {prev_log.get('source', prev_log.get('service', ''))} - {prev_log.get('message', '')}"
                    prev_tokens = len(self.encoding.encode(prev_log_str))
                    # Check if previous log itself was truncated in calculation, 
                    # but here we just estimate safely
                    if prev_tokens > 500: prev_tokens = 500
                    
                    if overlap_tokens + prev_tokens <= self.overlap:
                        overlap_chunk.insert(0, prev_log)
                        overlap_tokens += prev_tokens
                    else:
                        break
                current_chunk = overlap_chunk
                current_tokens = overlap_tokens

            current_chunk.append(log)
            current_tokens += tokens

        if current_chunk:
            start_time = current_chunk[0].get('timestamp', current_chunk[0].get('observed_at'))
            end_time = current_chunk[-1].get('timestamp', current_chunk[-1].get('observed_at'))
            chunks.append({
                "chunk_index": chunk_idx, 
                "logs": current_chunk,
                "start_time": start_time,
                "end_time": end_time
            })

        return chunks
