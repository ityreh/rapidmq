package de.ityreh.rapidmq.messaging;

import java.util.HashMap;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.core.MessagePostProcessor;
import org.springframework.amqp.core.MessageProperties;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import io.micrometer.observation.Observation;
import io.micrometer.observation.ObservationRegistry;
import io.micrometer.tracing.Tracer;
import io.micrometer.tracing.propagation.Propagator;

@RestController
public class MessagingController {
    private final RabbitTemplate rabbitTemplate;
    private final Tracer tracer;
    private final Propagator propagator;
    private final ObservationRegistry observationRegistry;
    private static final Logger logger = LoggerFactory.getLogger(MessagingController.class);

    @Value("${app.rabbitmq.exchange}")
    private String exchange;

    @Value("${app.rabbitmq.routingKey}")
    private String routingKey;

    public MessagingController(RabbitTemplate rabbitTemplate, Tracer tracer, Propagator propagator,
            ObservationRegistry observationRegistry) {
        this.rabbitTemplate = rabbitTemplate;
        this.tracer = tracer;
        this.propagator = propagator;
        this.observationRegistry = observationRegistry;
    }

    @PostMapping("/publish")
    public ResponseEntity<Map<String, String>> publish(@RequestBody Map<String, String> body) {
        String message = body.getOrDefault("message", "hello");

        Observation observation = Observation.start("rabbitmq.publish", observationRegistry);

        try (Observation.Scope scope = observation.openScope()) {
            MessagePostProcessor processor = msg -> {
                propagator.inject(tracer.currentTraceContext().context(),
                        msg.getMessageProperties(), MESSAGE_PROPERTIES_SETTER);
                return msg;
            };

            rabbitTemplate.convertAndSend(exchange, routingKey, message, processor);

            logger.info("Published message: {}", message);

            Map<String, String> response = new HashMap<>();
            response.put("status", "ok");
            response.put("message", message);
            return ResponseEntity.ok(response);
        } finally {
            observation.stop();
        }
    }

    private static final Propagator.Setter<MessageProperties> MESSAGE_PROPERTIES_SETTER =
            (carrier, key, value) -> {
                if (carrier != null) {
                    carrier.setHeader(key, value);
                }
            };
}
