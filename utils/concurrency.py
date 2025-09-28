# utils/concurrency.py
"""
Enhanced concurrency utilities with progress tracking and flexible patterns.

Provides thread-safe parallel processing with:
- Optional progress bars for long operations
- Batch processing for memory efficiency
- Rate limiting for API calls
- Comprehensive error handling
- Result aggregation patterns
"""

import time
import threading
import concurrent.futures
from tqdm import tqdm
from typing import List, Any, Callable, Optional, Dict, Tuple, TypeVar, Generic
from dataclasses import dataclass, field
from functools import wraps
from collections import defaultdict

from utils.logger import setup_logger

logger = setup_logger()

# Type variable for generic result types
T = TypeVar('T')


@dataclass
class ProcessingResult(Generic[T]):
    """
    Result container for parallel processing operations.

    Attributes:
        successful: List of successful results
        failed: List of (item, error) tuples for failures
        total_time: Total processing time in seconds
    """
    # Removed __slots__ due to conflict with field defaults

    successful: List[T] = field(default_factory=list)
    failed: List[Tuple[Any, Exception]] = field(default_factory=list)
    total_time: float = 0.0

    @property
    def success_count(self) -> int:
        """Number of successful operations."""
        return len(self.successful)

    @property
    def failure_count(self) -> int:
        """Number of failed operations."""
        return len(self.failed)

    @property
    def total_count(self) -> int:
        """Total number of operations."""
        return self.success_count + self.failure_count

    @property
    def success_rate(self) -> float:
        """Success rate as percentage."""
        if self.total_count == 0:
            return 0.0
        return (self.success_count / self.total_count) * 100


class ProgressTracker:
    """
    Thread-safe progress tracker for parallel operations.
    """

    def __init__(self, total: int, desc: str = "Processing",
                 show_progress: bool = True):
        """
        Initialize the progress tracker.

        Args:
            total: Total number of items to process
            desc: Description for progress bar
            show_progress: Whether to show progress bar
        """
        self.total = total
        self.desc = desc
        self.show_progress = show_progress
        self.completed = 0
        self._lock = threading.Lock()
        self._pbar = None

        if self.show_progress:
            self._init_progress_bar()

    def _init_progress_bar(self):
        """Initialize progress bar with lazy import."""
        # Hard-fail import - tqdm required for progress tracking
        self._pbar = tqdm(total=self.total, desc=self.desc,
                          unit="items", dynamic_ncols=True)

    def update(self, n: int = 1):
        """Update progress by n items."""
        with self._lock:
            self.completed += n
            if self._pbar:
                self._pbar.update(n)
            elif self.completed % max(1, self.total // 10) == 0:
                # Log progress every 10% if no progress bar
                pct = (self.completed / self.total) * 100
                logger.info(f"{self.desc}: {pct:.0f}% ({self.completed}/{self.total})")

    def close(self):
        """Close progress bar."""
        if self._pbar:
            self._pbar.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def run_parallel_environments(environments: List[Any],
                              process_func: Callable[[Any], bool],
                              show_progress: bool = False,
                              max_workers: Optional[int] = None) -> bool:
    """
    Process environments in parallel with optional progress tracking.

    Args:
        environments: List of environment dictionaries to process
        process_func: Function to process each environment
        show_progress: Whether to show progress bar
        max_workers: Maximum number of parallel workers (None = CPU count)

    Returns:
        True if all environments processed successfully
    """
    if not environments:
        logger.warning("No environments to process")
        return True

    all_success = True
    start_time = time.time()

    with ProgressTracker(len(environments), "Processing environments",
                         show_progress) as tracker:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_env = {
                executor.submit(process_func, env): env.get("id_env", "unknown")
                for env in environments
            }

            for future in concurrent.futures.as_completed(future_to_env):
                env_id = future_to_env[future]
                try:
                    env_success = future.result()
                    logger.debug(f"Environment {env_id} processed with success: {env_success}")
                    all_success = all_success and env_success
                except Exception as e:
                    logger.error(f"Error processing environment {env_id}: {e}", exc_info=True)
                    all_success = False
                finally:
                    tracker.update()

    elapsed = time.time() - start_time
    logger.info(f"Processed {len(environments)} environments in {elapsed:.2f}s "
                f"(success: {all_success})")

    return all_success


def parallel_map(func: Callable[[Any], T],
                 items: List[Any],
                 show_progress: bool = True,
                 max_workers: Optional[int] = None,
                 timeout: Optional[float] = None,
                 return_exceptions: bool = False) -> ProcessingResult[T]:
    """
    Map a function over items in parallel with progress tracking.

    Args:
        func: Function to apply to each item
        items: List of items to process
        show_progress: Whether to show progress bar
        max_workers: Maximum number of parallel workers
        timeout: Timeout for each operation in seconds
        return_exceptions: If True, exceptions are included in results

    Returns:
        ProcessingResult containing successful results and failures

    Example:
         def process_item(item):
        ...     return item * 2
         result = parallel_map(process_item, [1, 2, 3, 4, 5])
         print(f"Processed {result.success_count} items successfully")
    """
    if not items:
        return ProcessingResult()

    result = ProcessingResult[T]()
    start_time = time.time()

    desc = f"Processing {len(items)} items"
    with ProgressTracker(len(items), desc, show_progress) as tracker:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_item = {
                executor.submit(func, item): item
                for item in items
            }

            # Process completed futures
            for future in concurrent.futures.as_completed(future_to_item, timeout=timeout):
                item = future_to_item[future]
                try:
                    output = future.result()
                    result.successful.append(output)
                except Exception as e:
                    logger.debug(f"Error processing item {item}: {e}")
                    if return_exceptions:
                        result.successful.append(e)
                    else:
                        result.failed.append((item, e))
                finally:
                    tracker.update()

    result.total_time = time.time() - start_time

    logger.info(f"Parallel map completed: {result.success_count} successful, "
                f"{result.failure_count} failed, {result.total_time:.2f}s total")

    return result


def batch_process(func: Callable[[List[Any]], List[T]],
                  items: List[Any],
                  batch_size: int = 100,
                  show_progress: bool = True,
                  max_workers: Optional[int] = None) -> ProcessingResult[T]:
    """
    Process items in batches for memory efficiency.

    Args:
        func: Function that processes a batch of items
        items: List of all items to process
        batch_size: Number of items per batch
        show_progress: Whether to show progress bar
        max_workers: Maximum number of parallel workers

    Returns:
        ProcessingResult containing all results

    Example:
         def process_batch(batch):
        ...     return [item * 2 for item in batch]
         result = batch_process(process_batch, range(1000), batch_size=50)
    """
    if not items:
        return ProcessingResult()

    # Create batches
    batches = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]

    result = ProcessingResult[T]()
    start_time = time.time()

    desc = f"Processing {len(batches)} batches ({len(items)} items)"
    with ProgressTracker(len(batches), desc, show_progress) as tracker:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_batch = {
                executor.submit(func, batch): i
                for i, batch in enumerate(batches)
            }

            for future in concurrent.futures.as_completed(future_to_batch):
                batch_idx = future_to_batch[future]
                try:
                    batch_results = future.result()
                    result.successful.extend(batch_results)
                except Exception as e:
                    logger.error(f"Error processing batch {batch_idx}: {e}")
                    result.failed.append((f"batch_{batch_idx}", e))
                finally:
                    tracker.update()

    result.total_time = time.time() - start_time

    logger.info(f"Batch processing completed: {len(result.successful)} items processed, "
                f"{result.failure_count} batches failed, {result.total_time:.2f}s total")

    return result


def rate_limited_parallel(func: Callable[[Any], T],
                          items: List[Any],
                          calls_per_second: float = 10,
                          show_progress: bool = True,
                          max_workers: Optional[int] = None) -> ProcessingResult[T]:
    """
    Process items in parallel with rate limiting.

    Useful for API calls to avoid hitting rate limits.

    Args:
        func: Function to apply to each item
        items: List of items to process
        calls_per_second: Maximum calls per second
        show_progress: Whether to show progress bar
        max_workers: Maximum number of parallel workers

    Returns:
        ProcessingResult containing all results

    Example:
         def api_call(item):
        ...     return fetch_data(item)
         result = rate_limited_parallel(api_call, items, calls_per_second=5)
    """
    if not items:
        return ProcessingResult()

    from utils.api_common import RateLimiter

    rate_limiter = RateLimiter(calls_per_second=calls_per_second)

    def rate_limited_func(item):
        """Wrapper that applies rate limiting."""
        rate_limiter.wait_if_needed()
        return func(item)

    # Use parallel_map with rate-limited function
    return parallel_map(
        rate_limited_func,
        items,
        show_progress=show_progress,
        max_workers=max_workers
    )


def parallel_aggregate(func: Callable[[Any], Dict[str, Any]],
                       items: List[Any],
                       show_progress: bool = True,
                       max_workers: Optional[int] = None) -> Dict[str, List[Any]]:
    """
    Process items in parallel and aggregate results by key.

    Args:
        func: Function that returns a dict of results for each item
        items: List of items to process
        show_progress: Whether to show progress bar
        max_workers: Maximum number of parallel workers

    Returns:
        Dictionary with aggregated results by key

    Example:
         def analyze(item):
        ...     return {"type": item.type, "value": item.value}
         aggregated = parallel_aggregate(analyze, items)
         # Returns: {"type": [...], "value": [...]}
    """
    if not items:
        return {}

    aggregated = defaultdict(list)
    lock = threading.Lock()

    def process_and_aggregate(item):
        """Process item and aggregate results thread-safely."""
        item_result = func(item)
        with lock:
            for key, value in item_result.items():
                aggregated[key].append(value)
        return item_result

    # Process all items - Fixed variable shadowing
    processing_result = parallel_map(
        process_and_aggregate,
        items,
        show_progress=show_progress,
        max_workers=max_workers
    )

    logger.info(f"Aggregated {processing_result.success_count} items into {len(aggregated)} keys")

    return dict(aggregated)


def with_timeout(timeout_seconds: float):
    """
    Decorator to add timeout to any function.

    Args:
        timeout_seconds: Maximum execution time in seconds

    Example:
         @with_timeout(5.0)
        ... def slow_function():
        ...     time.sleep(10)
         slow_function()  # Will timeout after 5 seconds
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func, *args, **kwargs)
                try:
                    return future.result(timeout=timeout_seconds)
                except concurrent.futures.TimeoutError:
                    logger.error(f"Function {func.__name__} timed out after {timeout_seconds}s")
                    raise TimeoutError(f"Function timed out after {timeout_seconds}s")

        return wrapper

    return decorator


# Backward compatibility alias
def run_parallel(items: List[Any], func: Callable[[Any], Any],
                 **kwargs) -> ProcessingResult:
    """
    Backward compatible alias for parallel_map.

    Deprecated: Use parallel_map() instead.
    """
    logger.debug("run_parallel is deprecated. Use parallel_map() instead.")
    return parallel_map(func, items, **kwargs)