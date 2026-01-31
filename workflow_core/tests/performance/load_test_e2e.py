
import os
import sys
import time
import uuid
import grpc
import logging
from kafka import KafkaProducer
from google.protobuf.timestamp_pb2 import Timestamp

# Fix path to include src/proto_gen directly so generated code imports work
base_path = os.path.join(os.getcwd(), 'services/market-price-adapter-yfinance/src/proto_gen')
sys.path.append(base_path)

import market_data_pb2
import market_data_pb2_grpc

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("LoadTest")

def run_load_test():
    # Config
    kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP", "127.0.0.1:9093")
    grpc_target = os.getenv("GRPC_TARGET", "localhost:9002")
    topic = "market.candles"
    symbol = f"LOAD_TEST_{uuid.uuid4().hex[:8]}"
    count = 1000
    
    logger.info(f" Starting E2E Load Test for Symbol: {symbol}")
    logger.info(f" Target: Kafka={kafka_bootstrap}, gRPC={grpc_target}")

    # 1. Setup Producer
    producer = KafkaProducer(
        bootstrap_servers=kafka_bootstrap,
        key_serializer=lambda k: k.encode("utf-8"),
        value_serializer=lambda v: v
    )

    # 2. Publish Events (Write Path)
    start_time = time.time()
    
    logger.info(f" Publishing {count} candles...")
    for i in range(count):
        # Create Proto
        candle = market_data_pb2.Candle()
        candle.open = 100.0 + (i * 0.1)
        candle.high = 105.0
        candle.low = 95.0
        candle.close = 102.0
        candle.volume = 1000
        candle.interval = "1m"
        
        ts = Timestamp()
        ts.GetCurrentTime()
        
        event = market_data_pb2.MarketDataEvent()
        event.symbol = symbol
        event.provider = "load_test"
        event.event_timestamp.CopyFrom(ts)
        event.candle.CopyFrom(candle)

        producer.send(topic, key=symbol, value=event.SerializeToString())
    
    producer.flush()
    write_complete_time = time.time()
    logger.info(f" Publish Complete in {write_complete_time - start_time:.2f}s")

    # 3. Verify Persistence (Read Path) via gRPC
    # We poll until we see 'count' events or timeout
    with grpc.insecure_channel(grpc_target) as channel:
        stub = market_data_pb2_grpc.MarketPriceServiceStub(channel)
        
        poll_start = time.time()
        found = 0
        retries = 20 # 20 seconds timeout
        
        while found < count and retries > 0:
            try:
                # Query Range (Wide)
                req = market_data_pb2.GetMarketDataRequest()
                req.symbol = symbol
                # No time range = all
                
                response = stub.GetMarketData(req)
                found = len(response.events)
                print(f" Polling... Found {found}/{count}", end="\r")
                
                if found >= count:
                    break
            except Exception as e:
                logger.warning(f" gRPC Error: {e}")
            
            time.sleep(1)
            retries -= 1
        print("") # formatting

    end_time = time.time()
    
    # 4. Results
    if found >= count:
        total_duration = end_time - start_time
        throughput = count / total_duration
        logger.info("========================================")
        logger.info(" LOAD TEST PASSED ")
        logger.info(f" Total Duration: {total_duration:.2f}s")
        logger.info(f" Throughput: {throughput:.2f} candles/sec (E2E)")
        logger.info("========================================")
    else:
        logger.error(" LOAD TEST FAILED: Data Validation Timeout")
        sys.exit(1)

if __name__ == "__main__":
    run_load_test()
