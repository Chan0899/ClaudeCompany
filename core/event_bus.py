"""
事件总线 - 进程内发布/订阅, 驱动SSE实时推送
"""
import queue
import json
import time
import threading


class EventBus:
    """简易发布/订阅总线, 每个SSE客户端获取独立队列"""

    def __init__(self):
        self._subscribers: list[queue.Queue] = []
        self._lock = threading.Lock()

    def publish(self, event_type: str, data: dict):
        """向所有订阅者推送事件"""
        payload = json.dumps({
            "type": event_type,
            "data": data,
            "timestamp": time.time()
        }, ensure_ascii=False)

        with self._lock:
            dead = []
            for q in self._subscribers:
                try:
                    q.put_nowait(payload)
                except queue.Full:
                    dead.append(q)
            # 清理已满的队列 (客户端断开)
            for q in dead:
                self._subscribers.remove(q)

    def subscribe(self) -> queue.Queue:
        """新客户端订阅, 返回其专属消息队列"""
        q = queue.Queue(maxsize=256)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue):
        """客户端断开时取消订阅"""
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)


# 全局单例
event_bus = EventBus()
