BASE_TEMPLATE = """
You are an expert in program verification and testing. You are given a Java method and a postcondition assertion for that method.
Based on the method behavior, you will need to confirm that the method meets the postcondition.
If indeed the method meets the postcondition, you MUST output "OK".
If, on the other hand, you determine that the method does NOT meet the postcondition, you MUST output a counterexample, in the form of a jUnit test case. The counterexample test case MUST demonstrate the violation of the postcondition, using input values for the method that, after the execution of the method, make the postcondition invalid. You may provide the reasoning behind your ou

You will receive the input in the following way:
- The source code of the class comes first, after a line containing the text “[[CODE]]”
- The method under test, that the postcondition refers to, comes after the code, preceded by text “[[METHOD]]”
- The postcondition follows after the method, and is preceded by text “[[POSTCONDITION]]” (note: postconditions may include quantifiers like size(X) – returns the size of the collection X; pairwiseEqual(seq1, seq2) - True iff seq1 and seq2 have the same length, and every seq1[i] == seq2[i]; isReverse(seq1, seq2) - True iff seq1 is the reverse of seq2, typeArray(X) – returns the type of the array X; getElement(X, i) – returns the i-th element of the array X; old(X) – returns the value of X before executing the method under test; 

The output must be produced as follows:
- After text “[[VERDICT]]”, you will output “OK” if no counterexample for the method and postcondition exist, and “FAILED” otherwise.
- If verdict was “[[FAILED]]”, output the counterexample after the verdict, preceded by text “[[TEST]]”, in JUnit format.

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
assertTrue(a != b || b <= result);
[[VERDICT]]
OK
[[TEST]]
NONE

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
      public static int clamp(int x, int min, int max)
      {
        int result;
        if (x < min) {
            result = min;
        } else if (x > max) {
            result = max;
        } else {
            result = x;
        }

        assert (true);
        return result;
      }
}
[[METHOD]]
public static int clamp(int x, int min, int max)
{
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
assertTrue(orig(max) != -1 || result != 0);
[[VERDICT]]
FAILED
[[TEST]]
@Test
public void testClamp_1() {
    int x = -1;
    int min = 0;
    int max = -1;
    int origMax = max;

    int result = jts.MathUtil.clamp(x, min, max);

    assertTrue(origMax != -1 || result != 0);
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


  //static final long serialVersionUID = 20200617L;


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
      // The list should acyclic
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
assertTrue(this.x != this.next.next.x + orig(this.next.next.x));
[[VERDICT]]
FAILED
[[TEST]]
@Test
public void testInsert_1() {
    DataStructures.List list = new DataStructures.List();

    list.insert(-9);
    list.insert(-9);

    DataStructures.List origList = list.clone();

    list.insert(-18);

    assertTrue(list.x != list.next.next.x + origList.next.next.x);
}

"""
