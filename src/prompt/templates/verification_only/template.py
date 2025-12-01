BASE_TEMPLATE = """
You are an expert in Java program verification and specification reasoning.

You are given:
- The source code of a Java class.
- One method from that class (the method under test).
- A single postcondition assertion that refers to that method.

Your task is to determine whether the method satisfies the given postcondition for all possible executions (all valid inputs and states), assuming standard Java semantics.

If the method always satisfies the postcondition, you MUST consider the postcondition as VALID.
If you find that there exists some possible execution in which the postcondition does NOT hold, you MUST consider the postcondition as INVALID.

You will receive the input in the following format:

- After the line containing exactly [[CODE]], you will receive the full source code of the class.
- After the line containing exactly [[METHOD]], you will receive the source code of the method under test (this method is defined in the class above).
- After the line containing exactly [[POSTCONDITION]], you will receive a single postcondition expression about the method.

The postcondition language may include:
- size(X): returns the size of collection X.
- pairwiseEqual(seq1, seq2): true iff seq1 and seq2 have the same length and seq1[i] == seq2[i] for all i.
- isReverse(seq1, seq2): true iff seq2 is the reverse of seq1.
- typeArray(X): returns the type of the array X.
- getElement(X, i): returns the i-th element of array X.
- orig(E): the value of expression E before executing the method under test.
- Other standard logical and arithmetic operators over program variables, fields, and method parameters.

Your job is to reason about all possible behaviors of the method and decide if the postcondition is VALID or INVALID.

OUTPUT FORMAT (very important):

- After the line containing exactly [[VERDICT]], you MUST output a single JSON object.
- This JSON object must have exactly one key: the postcondition string you received after [[POSTCONDITION]] (including punctuation such as the final semicolon, if any).
- The value associated with that key must be the string "VALID" or "INVALID" depending on your conclusion.

For example, if the postcondition you received is:

[[POSTCONDITION]]
a != b || b <= result;

and you determine that it always holds, then after [[VERDICT]] you MUST output exactly:

{
    "a != b || b <= result;": "VALID"
}

If instead you determine that the postcondition does not always hold, you MUST output:

{
    "a != b || b <= result;": "INVALID"
}

STRICT OUTPUT REQUIREMENTS:

- Do NOT output any explanations, comments, or reasoning.
- Do NOT output any other text before or after the JSON object.
- Do NOT wrap the JSON object in code fences.
- Output ONLY the JSON object.

Here are some full examples of inputs and corresponding outputs:

[[CODE]]
package examples;

public class SimpleMethods {

    /**
     * Compute the minimum of two values
     *
     * @param a first value
     * @param b second value
     * @return a if a is lesser or equal to b, b otherwise
     */
    public int getMin(final int a, final int b) {
        final int result;
        if (a <= b) {
            result = a;
        } else {
            result = b;
        }
        return result;
    }
}
[[METHOD]]
public int getMin(final int a, final int b) {
    final int result;
    if (a <= b) {
        result = a;
    } else {
        result = b;
    }
    return result;
}
[[POSTCONDITION]]
a != b || b <= result;
[[VERDICT]]
{
    "a != b || b <= result;": "VALID"
}

[[CODE]]
package jts;
/**
 * <p>Operations on boolean primitives and Boolean objects.</p>
 *
 * <p>This class tries to handle {@code null} input gracefully.
 * An exception will not be thrown for a {@code null} input.
 * Each method documents its behaviour in more detail.</p>
 *
 * <p>#ThreadSafe#</p>
 * @since 2.0
 */
public class MathUtil {

    /**
     * Clamps an <tt>int</tt> value to a given range.
     * @param x the value to clamp
     * @param min the minimum value of the range
     * @param max the maximum value of the range
     * @return the clamped value
     */
    public static int clamp(int x, int min, int max) {
        int result;
        if (x < min) {
            result = min;
        } else if (x > max) {
            result = max;
        } else {
            result = x;
        }
        return result;
    }
}
[[METHOD]]
public static int clamp(int x, int min, int max) {
    int result;
    if (x < min) {
        result = min;
    } else if (x > max) {
        result = max;
    } else {
        result = x;
    }
    return result;
}
[[POSTCONDITION]]
orig(max) != -1 || result != 0;
[[VERDICT]]
{
    "orig(max) != -1 || result != 0;": "INVALID"
}

[[CODE]]
package DataStructures;

import java.io.Serializable;
import java.util.HashSet;
import java.util.Set;

/**
 * @author Facundo Molina <fmolina@dc.exa.unrc.edu.ar>
 */
public class List implements Serializable {

    int x;
    List next;

    static final int SENTINEL = Integer.MAX_VALUE;

    List(int x, List next) {
        this.x = x;
        this.next = next;
    }

    public List() {
        this(SENTINEL, null);
    }

    public void insert(int data) {
        if (data > this.x) {
            next.insert(data);
        } else {
            next = new List(x, next);
            x = data;
        }
    }

    public boolean repOk() {
        Set<List> visited = new HashSet<List>();
        List curr = this;
        while (curr.x != SENTINEL) {
            // The list should be acyclic
            if (!visited.add(curr))
                return false;
            // The list should be sorted
            List curr_next = curr.next;
            if (curr.x > curr_next.x)
                return false;

            curr = curr_next;
        }
        return true;
    }

    @Override
    public String toString() {
        if (x == SENTINEL) {
            return "null";
        } else {
            return x + ", " + next.toString();
        }
    }
}
[[METHOD]]
public void insert(int data) {
    if (data > this.x) {
        next.insert(data);
    } else {
        next = new List(x, next);
        x = data;
    }
}
[[POSTCONDITION]]
this.x != this.next.next.x + orig(this.next.next.x);
[[VERDICT]]
{
    "this.x != this.next.next.x + orig(this.next.next.x);": "INVALID"
}
"""
